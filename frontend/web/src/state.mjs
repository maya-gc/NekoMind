const EMPTY_JOURNEY = [
  { step: "capture", status: "waiting", duration_ms: null, provider: "mac", is_demo: false },
  { step: "transcription", status: "waiting", duration_ms: null, provider: "asr", is_demo: false },
  { step: "topics", status: "waiting", duration_ms: null, provider: "local_keywords", is_demo: false },
  { step: "result", status: "waiting", duration_ms: null, provider: "backend", is_demo: false },
];

const STEP_LABELS = {
  capture: "Captura",
  transcription: "Transcrição",
  topics: "Tópicos",
  result: "Resultado",
};

const STATE_COPY = {
  idle: "Toque para explicar",
  checking: "Verificando bancada",
  ready: "Pronto para começar",
  recording: "Ouvindo pelo Mac",
  paused: "Captura pausada",
  processing: "Preparando resposta",
  completed: "Resultado pronto",
  error: "Algo precisa de atenção",
  recovery: "Sessão interrompida",
  offline: "Backend local indisponível",
};

const STATUS_LABELS = {
  waiting: "aguardando",
  running: "executando",
  completed: "concluído",
  skipped: "ignorado",
  error: "erro",
  ready: "pronto",
  pending: "pendente",
};

export function routeFromPath(pathname = "/public") {
  if (pathname === "/touch") return { view: "touch" };
  if (pathname === "/presenter") return { view: "presenter" };
  return { view: "public" };
}

export function automaticDiagnosticForSnapshot(snapshot) {
  if (snapshot?.mode !== "real" || snapshot?.state !== "idle") return null;
  return {
    command: "diagnose",
    session_id: null,
    confirmed: false,
    mode: snapshot.experience_mode || "fair",
  };
}

export function fixtureSnapshot(name = "attraction") {
  const base = sanitizePublicSnapshot({
    schema_version: 1,
    generation: 1,
    session_id: null,
    state: "idle",
    mode: "demo",
    is_demo: true,
    experience_mode: "fair",
    diagnostics: [
      { component: "backend", status: "ready", message: "API local responde" },
      { component: "microfone", status: "pending", message: "Aguardando autoteste" },
      { component: "serial", status: "pending", message: "Emulador web" },
      { component: "provider", status: "ready", message: "Fixture QA" },
    ],
    journey: EMPTY_JOURNEY,
    voice: null,
    result: null,
    error: null,
    recovery: false,
    calibration: null,
    bridge_connected: true,
  }, { fixture: name });

  const fixtures = {
    attraction: base,
    checking: {
      ...base,
      generation: 2,
      state: "checking",
      diagnostics: [
        { component: "backend", status: "ready", message: "API local responde" },
        { component: "microfone", status: "ready", message: "Permissão validada" },
        { component: "captura", status: "pending", message: "Aguardando amostra" },
        { component: "serial", status: "ready", message: "Ponte conectada" },
      ],
    },
    "checking-error": {
      ...base,
      generation: 3,
      state: "error",
      diagnostics: [
        { component: "backend", status: "ready", message: "API local responde" },
        { component: "microfone", status: "error", message: "Selecione um microfone no Mac" },
        { component: "serial", status: "ready", message: "Ponte conectada" },
      ],
      error: { code: "mic_unavailable", message: "Microfone indisponível" },
    },
    ready: { ...base, generation: 4, state: "ready", mode: "real", is_demo: false },
    recording: {
      ...base,
      generation: 5,
      session_id: 128,
      state: "recording",
      mode: "real",
      is_demo: false,
      voice: { level: 68, clipping: false, quality: "ok" },
      journey: [
        { step: "capture", status: "running", duration_ms: 12000, provider: "mac", is_demo: false },
        ...EMPTY_JOURNEY.slice(1),
      ],
    },
    "low-voice": {
      ...base,
      generation: 6,
      session_id: 128,
      state: "recording",
      mode: "real",
      is_demo: false,
      voice: { level: 18, clipping: false, quality: "low" },
    },
    clipping: {
      ...base,
      generation: 7,
      session_id: 128,
      state: "recording",
      mode: "real",
      is_demo: false,
      voice: { level: 97, clipping: true, quality: "clipping" },
    },
    paused: { ...base, generation: 8, session_id: 128, state: "paused", mode: "real", is_demo: false },
    processing: {
      ...base,
      generation: 9,
      session_id: 128,
      state: "processing",
      mode: "real",
      is_demo: false,
      journey: [
        { step: "capture", status: "completed", duration_ms: 31000, provider: "mac", is_demo: false },
        { step: "transcription", status: "running", duration_ms: 2100, provider: "local-whisper", is_demo: false },
        { step: "topics", status: "waiting", duration_ms: null, provider: "local_keywords", is_demo: false },
        { step: "result", status: "waiting", duration_ms: null, provider: "backend", is_demo: false },
      ],
    },
    result: {
      ...base,
      generation: 1,
      session_id: 128,
      state: "completed",
      mode: "real",
      is_demo: false,
      journey: [
        { step: "capture", status: "completed", duration_ms: 31000, provider: "mac", is_demo: false },
        { step: "transcription", status: "completed", duration_ms: 2400, provider: "local-whisper", is_demo: false },
        { step: "topics", status: "completed", duration_ms: 180, provider: "local_keywords", is_demo: false },
        { step: "result", status: "completed", duration_ms: 410, provider: "backend", is_demo: false },
      ],
      result: {
        summary: "Você explicou osmose como passagem de água por uma membrana.",
        topics: ["osmose", "membrana", "concentração"],
        duration_seconds: 31,
        clarity_score: 0.82,
        subject: "biologia",
        metric_method_version: "heuristic-v1",
        trend: { duration_delta: -4, clarity_delta: 0.08 },
        asr_provider: "local-whisper",
        topic_provider: "local_keywords",
      },
    },
    error: {
      ...base,
      generation: 11,
      state: "error",
      error: { code: "backend_restarted", message: "Reconcilie a sessão antes de continuar" },
    },
    recovery: {
      ...base,
      generation: 12,
      session_id: 77,
      state: "recovery",
      recovery: true,
      error: { code: "session_interrupted", message: "Escolha retomar ou descartar" },
    },
    reset: { ...base, generation: 13, state: "idle", result: null, session_id: null },
  };

  for (const [fixtureName, active] of [["processing-topics", "topics"], ["processing-result", "result"]]) {
    fixtures[fixtureName] = { ...fixtures.processing, journey: fixtures.processing.journey.map((entry, index) => ({
      ...entry,
      status: entry.step === active ? "running" : index < (active === "topics" ? 2 : 3) ? "completed" : "waiting",
    })) };
  }
  return sanitizePublicSnapshot(fixtures[name] || base, { fixture: name });
}

export function sanitizePublicSnapshot(raw = {}, options = {}) {
  const result = raw.result && typeof raw.result === "object" ? {
    summary: stringOrEmpty(raw.result.summary),
    topics: Array.isArray(raw.result.topics) ? raw.result.topics.map(stringOrEmpty).filter(Boolean) : [],
    duration_seconds: numberOrNull(raw.result.duration_seconds),
    clarity_score: numberOrNull(raw.result.clarity_score),
    subject: stringOrNull(raw.result.subject),
    metric_method_version: stringOrNull(raw.result.metric_method_version),
    trend: raw.result.trend && typeof raw.result.trend === "object" ? raw.result.trend : null,
    asr_provider: stringOrNull(raw.result.asr_provider),
    topic_provider: stringOrNull(raw.result.topic_provider),
  } : null;

  return {
    schema_version: Number.isInteger(raw.schema_version) ? raw.schema_version : 1,
    generation: Number.isInteger(raw.generation) ? raw.generation : 0,
    session_id: raw.session_id ?? null,
    state: normalizeState(raw.state),
    mode: raw.mode === "real" ? "real" : "demo",
    is_demo: Boolean(raw.is_demo),
    experience_mode: raw.experience_mode === "normal" ? "normal" : "fair",
    diagnostics: sanitizeDiagnostics(raw.diagnostics),
    journey: sanitizeJourney(raw.journey),
    voice: sanitizeVoice(raw.voice),
    result,
    error: sanitizeError(raw.error),
    recovery: Boolean(raw.recovery),
    calibration: raw.calibration && typeof raw.calibration === "object" ? raw.calibration : null,
    bridge_connected: Boolean(raw.bridge_connected),
    fixture_label: options.fixture ? `QA fixture: ${options.fixture}` : null,
  };
}

export function sanitizePrivateSnapshot(raw = {}, options = {}) {
  const snapshot = sanitizePublicSnapshot(raw, options);
  return {
    ...snapshot,
    available_actions: Array.isArray(raw.available_actions) ? raw.available_actions.map(stringOrEmpty).filter(Boolean) : [],
    recoverable_sessions: sanitizeRecoverable(raw.recoverable_sessions),
    history: Array.isArray(raw.history) ? raw.history : [],
  };
}

export function touchModelForSnapshot(snapshot, options = {}) {
  const state = normalizeState(snapshot.state);
  const cards = resultCards(snapshot);
  const activeCard = cardModelForSnapshot(snapshot, {
    currentGeneration: options.currentGeneration,
    cardIndex: options.cardIndex || 0,
  });
  const voiceWarning = voiceWarningFor(snapshot.voice);

  return {
    view: "touch",
    state,
    mode: snapshot.mode,
    sessionLabel: shortSession(snapshot.session_id),
    title: voiceWarning || touchTitle(snapshot) || STATE_COPY[state] || STATE_COPY.idle,
    detail: touchDetail(snapshot),
    badges: badgesFor(snapshot, { emulator: options.emulator, fixture: options.fixture }),
    diagnostics: snapshot.diagnostics,
    journey: snapshot.journey,
    voice: snapshot.voice,
    result: snapshot.result,
    error: snapshot.error,
    recovery: snapshot.recovery,
    cards,
    activeCard,
    activeStatus: voiceWarning ? null : touchStatusCard(snapshot, options.statusIndex || 0),
    primaryAction: primaryActionFor(state, snapshot),
    secondaryActions: secondaryActionsFor(state, snapshot),
  };
}

export function cardModelForSnapshot(snapshot, cardState = {}) {
  const cards = resultCards(snapshot);
  if (!cards.length) return { cardIndex: 0, card: null, generation: snapshot.generation };
  const generationChanged = cardState.currentGeneration !== snapshot.generation;
  const index = generationChanged ? 0 : Math.min(Math.max(cardState.cardIndex || 0, 0), cards.length - 1);
  return { cardIndex: index, card: cards[index], generation: snapshot.generation, total: cards.length };
}

export function resultCards(snapshot) {
  if (!snapshot.result) return [];
  const cards = [
    ...chunkText(snapshot.result.summary || "Sem resumo público.").map((value, index, chunks) => ({
      kind: "summary",
      label: chunks.length > 1 ? `Resumo ${index + 1}` : "Resumo",
      value,
    })),
    ...(snapshot.result.topics.length
      ? snapshot.result.topics.flatMap((topic, index) => chunkText(topic).map((value, chunkIndex, chunks) => ({
        kind: "topic",
        label: chunkIndex === 0 ? `Tópico ${index + 1}` : `Tópico ${index + 1}.${chunkIndex + 1}`,
        value,
      })))
      : [{ kind: "topic", label: "Tópicos", value: "Sem tópicos públicos." }]),
    { kind: "duration", label: "Duração", value: `${snapshot.result.duration_seconds ?? 0}s explicando` },
  ];
  const trendCards = trendCardsFor(snapshot.result.trend);
  if (trendCards.length) {
    cards.push(...trendCards);
  }
  return cards;
}

export function stepLabel(step) {
  return STEP_LABELS[step] || step;
}

export function statusLabel(status) {
  return STATUS_LABELS[status] || status;
}

export function createCommandQueue({ send, createRequestId, checkStatus = null, pollDelayMs = 500, timeoutMs = 12000 }) {
  let pendingPromise = null;
  const retryBySignature = new Map();
  let lastError = "";

  return {
    enqueue(command) {
      if (pendingPromise) return pendingPromise;
      const signature = commandSignature(command);
      const requestId = retryBySignature.get(signature) || createRequestId();
      const payload = { request_id: requestId, ...command };
      pendingPromise = Promise.resolve(send(payload))
        .then((response) => waitForCommandAck(payload, response, { checkStatus, pollDelayMs, timeoutMs }))
        .then((response) => {
          retryBySignature.delete(signature);
          lastError = "";
          return response;
        })
        .catch((error) => {
          if (error?.definitive) {
            retryBySignature.delete(signature);
          } else {
            retryBySignature.set(signature, requestId);
          }
          lastError = error?.message || "Falha ao enviar comando";
          throw error;
        })
        .finally(() => {
          pendingPromise = null;
        });
      return pendingPromise;
    },
    getState() {
      return {
        pending: Boolean(pendingPromise),
        retryRequestId: retryBySignature.values().next().value || null,
        lastError,
      };
    },
    clearRetry() {
      retryBySignature.clear();
      lastError = "";
    },
  };
}

async function waitForCommandAck(payload, response, options) {
  if (!options.checkStatus || !isQueuedResponse(response)) return response;
  const start = Date.now();
  while (Date.now() - start < options.timeoutMs) {
    const status = await options.checkStatus(payload.request_id);
    if (status.status === "pending") {
      await delay(options.pollDelayMs);
      continue;
    }
    if (status.status === "superseded") {
      throw definitiveCommandError("Comando substituído antes da confirmação do Mac");
    }
    if (status.response?.type === "error" || status.response?.code) {
      throw definitiveCommandError(status.response.code || "Erro confirmado pelo Mac");
    }
    return status.response || status;
  }
  throw new Error("Comando aceito, mas sem confirmação do Mac no tempo esperado");
}

function isQueuedResponse(response) {
  return response?.readyState === "queued" || response?.status === "queued" || response?.accepted === true;
}

function definitiveCommandError(message) {
  const error = new Error(message);
  error.definitive = true;
  return error;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function touchStatusCard(snapshot, requestedIndex) {
  if (snapshot.state === "checking") {
    const diagnostics = snapshot.diagnostics.length ? snapshot.diagnostics : [{ component: "autoteste", status: "pending", message: "Aguardando resposta" }];
    const index = boundedIndex(requestedIndex, diagnostics.length);
    const item = diagnostics[index];
    return {
      type: "diagnostic",
      index,
      total: diagnostics.length,
      title: item.component,
      status: statusLabel(item.status),
      detail: item.message,
    };
  }
  if (snapshot.state === "recording" || snapshot.state === "processing") {
    const index = boundedIndex(requestedIndex, snapshot.journey.length);
    const step = snapshot.journey[index] || snapshot.journey[0];
    if (!step) return null;
    return {
      type: "journey",
      index,
      total: snapshot.journey.length,
      title: stepLabel(step.step),
      status: statusLabel(step.status),
      detail: humanDuration(step.duration_ms),
    };
  }
  return null;
}

function sanitizeRecoverable(items) {
  if (!Array.isArray(items)) return [];
  return items.map((item) => ({
    session_id: item.session_id ?? item.id ?? null,
    state: stringOrEmpty(item.state || item.status),
    subject: stringOrNull(item.subject),
  })).filter((item) => item.session_id !== null && item.session_id !== undefined);
}

function sanitizeDiagnostics(items) {
  if (!Array.isArray(items)) return [];
  return items.map((item) => ({
    component: stringOrEmpty(item.component),
    status: ["ready", "error", "pending", "skipped"].includes(item.status) ? item.status : "pending",
    message: stringOrEmpty(item.message),
  })).filter((item) => item.component);
}

function sanitizeJourney(items) {
  const source = Array.isArray(items) && items.length ? items : EMPTY_JOURNEY;
  return source.map((item) => ({
    step: stringOrEmpty(item.step),
    status: ["waiting", "running", "completed", "skipped", "error"].includes(item.status) ? item.status : "waiting",
    duration_ms: numberOrNull(item.duration_ms),
    provider: stringOrEmpty(item.provider),
    is_demo: Boolean(item.is_demo),
  })).filter((item) => item.step);
}

function sanitizeVoice(voice) {
  if (!voice || typeof voice !== "object") return null;
  return {
    level: Math.max(0, Math.min(100, Number(voice.level) || 0)),
    clipping: Boolean(voice.clipping),
    quality: ["ok", "low", "clipping", "unknown"].includes(voice.quality) ? voice.quality : "unknown",
  };
}

function sanitizeError(error) {
  if (!error || typeof error !== "object") return null;
  return { code: stringOrEmpty(error.code), message: stringOrEmpty(error.message) };
}

function normalizeState(state) {
  return ["idle", "checking", "ready", "recording", "paused", "processing", "completed", "error", "recovery", "offline"].includes(state)
    ? state
    : "idle";
}

function primaryActionFor(state, snapshot) {
  const actions = {
    idle: { label: "Verificar", command: "diagnose" },
    checking: { label: "Verificando", command: null, disabled: true },
    ready: { label: "Começar", command: "start" },
    recording: { label: "Finalizar", command: "finish" },
    paused: { label: "Retomar", command: "resume" },
    processing: { label: "Aguardar evento", command: null, disabled: true },
    completed: { label: "Tentar novamente", command: "retry" },
    error: { label: "Diagnóstico", command: "diagnose" },
    recovery: { label: "Retomar", command: "recover", confirmed: true },
    offline: { label: "Reconectar", command: "diagnose" },
  };
  return { minTouchTargetPx: 56, ...actions[state], session_id: snapshot.session_id };
}

function secondaryActionsFor(state, snapshot) {
  if (state === "recording") return [{ label: "Pausar", command: "pause", session_id: snapshot.session_id }];
  if (state === "paused") return [{ label: "Finalizar", command: "finish", session_id: snapshot.session_id }];
  if (state === "recovery") return [{ label: "Descartar", command: "discard", confirmed: true, session_id: snapshot.session_id }];
  if (state === "completed") return [{ label: "Encerrar", command: "reset", confirmed: true, session_id: snapshot.session_id }];
  if (state === "error") return [{ label: "Reset feira", command: "reset", confirmed: true, session_id: snapshot.session_id }];
  return [];
}

function badgesFor(snapshot, options) {
  const badges = [
    { text: snapshot.mode === "real" ? "REAL" : "DEMO", tone: snapshot.mode },
    { text: snapshot.bridge_connected ? "ok" : "offline", tone: snapshot.bridge_connected ? "ok" : "warn" },
  ];
  if (snapshot.session_id !== null && snapshot.session_id !== undefined) {
    badges.push({ text: shortSession(snapshot.session_id), tone: "id" });
  }
  if (options.emulator) badges.push({ text: "EMULADOR", tone: "demo" });
  if (options.fixture || snapshot.fixture_label) {
    badges.push({ text: "QA", title: snapshot.fixture_label || `QA fixture: ${options.fixture}`, tone: "fixture" });
  }
  return badges;
}

function touchTitle(snapshot) {
  if (snapshot.state === "processing") {
    const step = activeJourneyStep(snapshot);
    const labels = {
      capture: "Capturando",
      transcription: "Transcrevendo",
      topics: "Extraindo tópicos",
      result: "Preparando resultado",
    };
    return labels[step?.step] || "Preparando resposta";
  }
  return null;
}

function touchDetail(snapshot) {
  if (snapshot.error?.message) return snapshot.error.message;
  if (snapshot.state === "recording") return "A captura vem do Mac. O navegador não grava áudio.";
  if (snapshot.state === "paused") return "A captura está pausada. Toque em Retomar quando quiser continuar.";
  if (snapshot.state === "processing") return "Aguarde a bancada confirmar esta etapa.";
  if (snapshot.state === "completed") return "Cartões limpos para o próximo visitante.";
  if (snapshot.state === "recovery") return "Escolha uma ação explícita antes de reabrir captura.";
  return "Explique em voz alta quando a bancada confirmar prontidão.";
}

function voiceWarningFor(voice) {
  if (!voice) return null;
  if (voice.clipping || voice.quality === "clipping") return "Muito alto";
  if (voice.quality === "low") return "Fale um pouco mais perto";
  return null;
}

function chunkText(text, maxLength = 32) {
  const clean = stringOrEmpty(text).trim();
  if (!clean) return [""];
  if (clean.length <= maxLength) return [clean];
  const chunks = [];
  let remaining = clean;
  while (remaining.length > maxLength) {
    const boundary = remaining.lastIndexOf(" ", maxLength);
    const splitAt = boundary > 0 ? boundary : maxLength;
    chunks.push(remaining.slice(0, splitAt).trim());
    remaining = remaining.slice(splitAt).trim();
  }
  if (remaining) chunks.push(remaining);
  return chunks;
}

function activeJourneyStep(snapshot) {
  const index = snapshot.journey.findIndex((step) => step.status === "running" || step.status === "error");
  return snapshot.journey[index === -1 ? 0 : index] || null;
}

function humanDuration(durationMs) {
  if (durationMs === null || durationMs === undefined) return "aguardando duração";
  const seconds = Math.max(1, Math.round(Number(durationMs) / 1000));
  return `${seconds}s`;
}

function trendCardsFor(rawTrend) {
  if (!rawTrend || typeof rawTrend !== "object") return [];
  const values = rawTrend.trend && typeof rawTrend.trend === "object" ? rawTrend.trend : rawTrend;
  const method = rawTrend.method_version || rawTrend.metric_method_version || "";
  const disclaimer = rawTrend.disclaimer || "Compare somente sessões do mesmo assunto confirmado.";
  const parts = [];
  if (Number.isFinite(Number(values.duration_seconds_delta))) {
    parts.push(`duração ${signedNumber(values.duration_seconds_delta)}s`);
  }
  if (Number.isFinite(Number(values.clarity_score_delta))) {
    parts.push(`clareza ${signedNumber(values.clarity_score_delta)}`);
  }
  if (Number.isFinite(Number(values.topic_count_delta))) {
    parts.push(`tópicos ${signedNumber(values.topic_count_delta)}`);
  }
  if (!parts.length) return [];
  const methodText = method ? ` método ${method}.` : "";
  return chunkText(`${parts.join(" · ")}.${methodText} ${disclaimer}`).map((value, index, chunks) => ({
    kind: "trend",
    label: chunks.length > 1 ? `Evolução ${index + 1}` : "Evolução",
    value,
  }));
}

function signedNumber(value) {
  const number = Number(value);
  return number > 0 ? `+${number}` : String(number);
}

function boundedIndex(index, total) {
  return Math.min(Math.max(Number(index) || 0, 0), Math.max(total - 1, 0));
}

function commandSignature(command) {
  return JSON.stringify({
    command: command.command,
    session_id: command.session_id ?? null,
    confirmed: Boolean(command.confirmed),
    mode: command.mode || null,
  });
}

function shortSession(sessionId) {
  return sessionId === null || sessionId === undefined ? "sem sessão" : `S${String(sessionId).slice(-4)}`;
}

function stringOrEmpty(value) {
  return typeof value === "string" ? value : "";
}

function stringOrNull(value) {
  return typeof value === "string" && value ? value : null;
}

function numberOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  return Number.isFinite(Number(value)) ? Number(value) : null;
}
