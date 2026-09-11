import assert from "node:assert/strict";
import test from "node:test";

import {
  cardModelForSnapshot,
  fixtureSnapshot,
  routeFromPath,
  sanitizePublicSnapshot,
  sanitizePrivateSnapshot,
  createCommandQueue,
  resultCards,
  touchModelForSnapshot,
} from "../web/src/state.mjs";
import {
  renderCatFace,
  renderCommandState,
  renderConfirmation,
  renderHistory,
  renderPresenter,
  renderPublic,
  renderTouch,
} from "../web/src/render.mjs";
import { createExperienceClient } from "../web/src/api.mjs";

test("destructive confirmation is accessible, escaped and offers explicit cancellation", () => {
  const html = renderConfirmation('<img src=x onerror=alert(1)>');
  assert.match(html, /role="alertdialog"/);
  assert.match(html, /aria-modal="true"/);
  assert.match(html, /data-confirm-answer="yes"/);
  assert.match(html, /data-confirm-answer="no"/);
  assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<img/);
});

test("routeFromPath resolves the three static routes without changing auth state", () => {
  assert.equal(routeFromPath("/touch").view, "touch");
  assert.equal(routeFromPath("/public").view, "public");
  assert.equal(routeFromPath("/presenter").view, "presenter");
  assert.equal(routeFromPath("/unknown").view, "public");
});

test("completed result starts a deliberate retry tied to the previous session", () => {
  const model = touchModelForSnapshot(fixtureSnapshot("result"));
  assert.equal(model.primaryAction.command, "retry");
  assert.equal(model.primaryAction.session_id, 128);
});

test("unauthenticated presenter does not claim there are no interrupted sessions", () => {
  const html = renderPresenter(fixtureSnapshot("recovery"), { hasToken: false });
  assert.doesNotMatch(html, /Sem recuperação pendente/);
  assert.match(html, /Informe o token para consultar recuperações/);
});

test("public snapshots are sanitized and fixture mode is visibly labelled", () => {
  const raw = {
    schema_version: 1,
    generation: 7,
    session_id: 42,
    state: "completed",
    mode: "real",
    is_demo: false,
    transcript: "texto privado que nunca deve aparecer",
    operator_token: "secret",
    result: {
      summary: "Resumo seguro",
      topics: ["capilaridade", "osmose"],
      duration_seconds: 38,
      clarity_score: 0.81,
      subject: "biologia",
      metric_method_version: "heuristic-v1",
      trend: null,
      asr_provider: "local-whisper",
      topic_provider: "local_keywords",
      transcript: "privado tambem",
    },
  };

  const snapshot = sanitizePublicSnapshot(raw, { fixture: "result" });

  assert.equal(snapshot.fixture_label, "QA fixture: result");
  assert.equal(snapshot.result.summary, "Resumo seguro");
  assert.equal(snapshot.transcript, undefined);
  assert.equal(snapshot.operator_token, undefined);
  assert.equal(snapshot.result.transcript, undefined);
  assert.match(renderPublic(snapshot), /QA fixture: result/);
  assert.doesNotMatch(renderPublic(snapshot), /texto privado|secret|transcript/i);
  assert.doesNotMatch(renderPublic(snapshot), /Cancelar|Resetar|Diagnóstico/i);
});

test("touch model keeps the cat dominant, labels emulator mode, and resets cards by generation", () => {
  const result = fixtureSnapshot("result");
  const firstCard = cardModelForSnapshot(result, { currentGeneration: 1, cardIndex: 3 });
  const resetCard = cardModelForSnapshot(result, { currentGeneration: 999, cardIndex: 3 });
  const model = touchModelForSnapshot(result, { fixture: "result", emulator: true });
  const html = renderTouch(model);

  assert.equal(firstCard.cardIndex, 3);
  assert.equal(resetCard.cardIndex, 0);
  assert.equal(model.badges.some((badge) => badge.text === "EMULADOR"), true);
  assert.equal(model.primaryAction.minTouchTargetPx >= 44, true);
  assert.match(html, /Rosto-instrumento/);
  assert.match(html, /EMULADOR/);
  assert.match(html, /title="QA fixture: result"/);
  assert.doesNotMatch(html, /getUserMedia|microfone do navegador|browser mic/i);
});

test("touch rendering stays contained on 240x320 with compact status cards", () => {
  const recording = renderTouch(touchModelForSnapshot(fixtureSnapshot("recording"), {
    fixture: "recording",
    emulator: true,
  }));
  const checking = renderTouch(touchModelForSnapshot(fixtureSnapshot("checking"), {
    fixture: "checking",
    emulator: true,
    statusIndex: 1,
  }));

  assert.doesNotMatch(recording, /journey-list|diagnostic-list/);
  assert.doesNotMatch(checking, /journey-list|diagnostic-list/);
  assert.match(recording, /touch-status-card/);
  assert.match(checking, /1 de 4|2 de 4/);
  assert.match(recording, />QA</);
  assert.match(recording, />EMULADOR</);
});

test("touch warning, paused, result and error actions stay operator-safe", () => {
  const lowVoice = renderTouch(touchModelForSnapshot(fixtureSnapshot("low-voice")));
  const paused = renderTouch(touchModelForSnapshot(fixtureSnapshot("paused")));
  const result = renderTouch(touchModelForSnapshot(fixtureSnapshot("result")));
  const error = renderTouch(touchModelForSnapshot({
    ...fixtureSnapshot("error"),
    error: { code: "mic_unavailable", message: "Microfone indisponível" },
  }));
  const recovery = renderTouch(touchModelForSnapshot(fixtureSnapshot("recovery")));

  assert.match(lowVoice, /Fale um pouco mais perto/);
  assert.doesNotMatch(lowVoice, /touch-status-card/);
  assert.match(paused, /Retomar/);
  assert.match(paused, /Finalizar/);
  assert.match(result, /Tentar novamente/);
  assert.match(result, /Encerrar/);
  assert.doesNotMatch(result, /Ver cartões/);
  assert.doesNotMatch(error, /mic_unavailable/);
  assert.doesNotMatch(recovery, /session_interrupted/);
});

test("touch status hides provider details and keeps student text simple", () => {
  const model = touchModelForSnapshot(fixtureSnapshot("recording"));
  const html = renderTouch(model);

  assert.match(html, /12s/);
  assert.doesNotMatch(html, /mac ·|local-whisper|provider|ms/i);
});

test("cat face and required state contracts render for all central states", () => {
  const states = [
    "idle",
    "checking",
    "ready",
    "recording",
    "paused",
    "processing",
    "completed",
    "error",
    "recovery",
  ];

  for (const state of states) {
    const html = renderCatFace({ state, voice: { level: 62, clipping: false, quality: "ok" } });
    assert.match(html, /<svg/);
    assert.match(html, /aria-label="Rosto-instrumento NekoMind/);
    assert.match(html, new RegExp(`data-state="${state}"`));
  }
});

test("voice warning and cat low state require explicit backend quality", () => {
  const idleWithLevelZero = touchModelForSnapshot({
    ...fixtureSnapshot("attraction"),
    voice: { level: 0, clipping: false, quality: "ok" },
  });
  const lowVoice = touchModelForSnapshot(fixtureSnapshot("low-voice"));

  assert.equal(idleWithLevelZero.title, "Toque para explicar");
  assert.match(lowVoice.title, /Fale um pouco mais perto/);
  assert.doesNotMatch(renderCatFace({ state: "idle", voice: { level: 0, clipping: false, quality: "ok" } }), /is-low/);
});

test("presenter keeps token in memory and sends bearer only to reserved APIs", async () => {
  const calls = [];
  const client = createExperienceClient({
    fetchImpl: async (url, init = {}) => {
      calls.push({ url: String(url), init });
      return {
        ok: true,
        status: 200,
        json: async () => ({ readyState: "queued", request_id: "rid-1" }),
      };
    },
    tokenProvider: () => "operator-token",
  });

  await client.getPublic();
  await client.getPresenter();
  await client.enqueueCommand({
    request_id: "rid-1",
    command: "reset",
    session_id: 42,
    confirmed: true,
    mode: "fair",
  });

  assert.equal(calls[0].url, "/api/v1/experience/public");
  assert.equal(calls[0].init.headers?.Authorization, undefined);
  assert.equal(calls[1].url, "/api/v1/experience/presenter");
  assert.equal(calls[1].init.headers.Authorization, "Bearer operator-token");
  assert.equal(calls[2].url.includes("operator-token"), false);
  assert.equal(calls[2].init.headers.Authorization, "Bearer operator-token");
  assert.deepEqual(JSON.parse(calls[2].init.body), {
    request_id: "rid-1",
    command: "reset",
    session_id: 42,
    confirmed: true,
    mode: "fair",
  });
});

test("presenter render exposes diagnostics and safe confirmations without secrets", () => {
  const privateSnapshot = sanitizePrivateSnapshot({
    ...fixtureSnapshot("recovery"),
    available_actions: ["diagnose", "recover", "discard", "reset"],
    recoverable_sessions: [{ id: 12, status: "recovery", subject: "matematica" }],
  });
  const html = renderPresenter(privateSnapshot, { hasToken: true });

  assert.match(html, /Diagnóstico/);
  assert.match(html, /Calibrar/);
  assert.match(html, /Cancelar sessão/);
  assert.match(html, /Reset feira/);
  assert.match(html, /Confirmar assunto/);
  assert.match(html, /Corrigir assunto/);
  assert.match(html, /Histórico/);
  assert.match(html, /Excluir sessão/);
  assert.match(html, /Ver resultado/);
  assert.match(html, /name="experience-mode"/);
  assert.match(html, /S12 · matematica · recovery/);
  assert.match(html, /confirmed/);
  assert.doesNotMatch(html, /operator-token|Bearer|localStorage|transcrição completa/i);
});

test("rendered command errors and history escape markup and avoid raw JSON", () => {
  const malicious = '<img src=x onerror="globalThis.__xss=1">';
  const commandHtml = renderCommandState({ pendingCommand: false, commandError: malicious });
  const historyHtml = renderHistory({
    points: [
      {
        session_id: 44,
        created_at: "2026-09-11T12:00:00Z",
        duration_seconds: 31,
        clarity_score: 0.82,
        topics: ["osmose", malicious],
        metric_method_version: "heuristic-v1",
      },
    ],
    trend: {
      duration_seconds_delta: -4,
      clarity_score_delta: 0.08,
      topic_count_delta: 1,
    },
    method_version: "heuristic-v1",
    disclaimer: "Tendência não prova domínio.",
  });

  assert.match(commandHtml, /&lt;img/);
  assert.doesNotMatch(commandHtml, /<img/);
  assert.match(historyHtml, /S44/);
  assert.match(historyHtml, /31s/);
  assert.match(historyHtml, /0.82/);
  assert.match(historyHtml, /heuristic-v1/);
  assert.match(historyHtml, /Tendência não prova domínio/);
  assert.doesNotMatch(historyHtml, /"points"|\{|\}|<img/);
});

test("result cards paginate topics and long phrases instead of overflowing one card", () => {
  const longTopic = "fotossíntese ".repeat(14).trim();
  const snapshot = sanitizePublicSnapshot({
    ...fixtureSnapshot("result"),
    result: {
      ...fixtureSnapshot("result").result,
      summary: "Resumo ".repeat(30).trim(),
      topics: Array.from({ length: 8 }, (_, index) => `${index + 1} ${longTopic}`),
    },
  });
  const cards = resultCards(snapshot);

  assert.equal(cards.filter((card) => card.kind === "topic").length >= 8, true);
  assert.equal(cards.every((card) => card.value.length <= 70), true);
  assert.equal(cards.some((card) => card.label === "Tópico 8"), true);
});

test("result cards show real trend deltas only when backend provides them", () => {
  const noTrend = resultCards({
    ...fixtureSnapshot("result"),
    result: { ...fixtureSnapshot("result").result, trend: null },
  });
  const withTrend = resultCards(sanitizePublicSnapshot({
    ...fixtureSnapshot("result"),
    result: {
      ...fixtureSnapshot("result").result,
      trend: {
        trend: {
          duration_seconds_delta: -6,
          clarity_score_delta: 0.12,
          topic_count_delta: 2,
        },
        method_version: "heuristic-v2",
        disclaimer: "Tendência local entre sessões do mesmo assunto.",
      },
    },
  }));

  assert.equal(noTrend.some((card) => card.kind === "trend"), false);
  assert.equal(withTrend.some((card) => card.value.includes("-6s")), true);
  assert.equal(withTrend.some((card) => card.value.includes("+0.12")), true);
  assert.equal(withTrend.some((card) => card.value.includes("heuristic-v2")), true);
});

test("processing title carries current step when compact landscape hides status card", () => {
  const model = touchModelForSnapshot(fixtureSnapshot("processing"));

  assert.match(model.title, /Transcrevendo|Capturando|Extraindo|Preparando/);
  assert.doesNotMatch(model.detail, /eventos recebidos|provider|ms/i);
});

test("public processing copy avoids real-only and technical student jargon", () => {
  const html = renderPublic({ ...fixtureSnapshot("processing"), mode: "demo", is_demo: true });

  assert.match(html, /Jornada da sessão/);
  assert.doesNotMatch(html, /Jornada real/);
  assert.doesNotMatch(html, /backend local|evento/i);
});

test("public result avoids duplicated summary box and keeps topics visible without admin copy", () => {
  const html = renderPublic(fixtureSnapshot("result"));

  assert.doesNotMatch(html, /result-summary/);
  assert.match(html, /topic-strip/);
  assert.match(html, /osmose/);
  assert.equal((html.match(/Você explicou osmose/g) || []).length, 1);
});

test("command queue locks pending commands and retries failures with the same request id", async () => {
  const calls = [];
  let shouldFail = true;
  const queue = createCommandQueue({
    createRequestId: () => `rid-${calls.length + 1}`,
    send: async (payload) => {
      calls.push(payload);
      if (shouldFail) {
        shouldFail = false;
        throw new Error("token inválido");
      }
      return { readyState: "queued" };
    },
  });

  await assert.rejects(
    () => queue.enqueue({ command: "diagnose", session_id: null, confirmed: false, mode: "fair" }),
    /token inválido/,
  );
  assert.equal(queue.getState().lastError, "token inválido");

  const retry = await queue.enqueue({ command: "diagnose", session_id: null, confirmed: false, mode: "fair" });
  assert.equal(retry.readyState, "queued");
  assert.equal(calls[0].request_id, "rid-1");
  assert.equal(calls[1].request_id, "rid-1");

  let release;
  const pendingQueue = createCommandQueue({
    createRequestId: () => "rid-lock",
    send: (payload) => new Promise((resolve) => {
      calls.push(payload);
      release = () => resolve({ readyState: "queued" });
    }),
  });
  const first = pendingQueue.enqueue({ command: "reset", session_id: 1, confirmed: true, mode: "fair" });
  const second = pendingQueue.enqueue({ command: "reset", session_id: 1, confirmed: true, mode: "fair" });

  assert.equal(pendingQueue.getState().pending, true);
  release();
  assert.deepEqual(await second, await first);
  assert.equal(calls.filter((call) => call.request_id === "rid-lock").length, 1);
});

test("command queue keeps retry request ids scoped to the same command payload", async () => {
  const calls = [];
  let failStart = true;
  const queue = createCommandQueue({
    createRequestId: () => `rid-${calls.length + 1}`,
    send: async (payload) => {
      calls.push(payload);
      if (payload.command === "start" && failStart) {
        failStart = false;
        throw new Error("queda de rede");
      }
      return { readyState: "queued" };
    },
  });

  await assert.rejects(
    () => queue.enqueue({ command: "start", session_id: null, confirmed: false, mode: "fair" }),
    /queda de rede/,
  );
  await queue.enqueue({ command: "cancel", session_id: 55, confirmed: true, mode: "fair" });
  await queue.enqueue({ command: "start", session_id: null, confirmed: false, mode: "fair" });

  assert.equal(calls[0].request_id, "rid-1");
  assert.notEqual(calls[1].request_id, "rid-1");
  assert.equal(calls[2].request_id, "rid-1");
});

test("command queue waits for Mac ack status and surfaces command receipt errors", async () => {
  const statuses = [
    { status: "pending", response: null },
    { status: "done", response: { request_id: "rid-ack", session_id: 5, type: "state", state: "recording" } },
  ];
  const queue = createCommandQueue({
    createRequestId: () => "rid-ack",
    send: async (payload) => ({ request_id: payload.request_id, accepted: true }),
    checkStatus: async () => statuses.shift(),
    pollDelayMs: 0,
    timeoutMs: 200,
  });

  const response = await queue.enqueue({ command: "start", session_id: null, confirmed: false, mode: "fair" });
  assert.equal(response.state, "recording");

  const errorQueue = createCommandQueue({
    createRequestId: () => "rid-error",
    send: async (payload) => ({ status: "queued", request_id: payload.request_id }),
    checkStatus: async () => ({ status: "done", response: { request_id: "rid-error", type: "error", code: "mic_unavailable" } }),
    pollDelayMs: 0,
    timeoutMs: 200,
  });

  await assert.rejects(
    () => errorQueue.enqueue({ command: "start", session_id: null, confirmed: false, mode: "fair" }),
    /mic_unavailable/,
  );
  assert.equal(errorQueue.getState().lastError, "mic_unavailable");
});

test("command queue retries network timeouts with same id but uses new id after definitive Mac errors", async () => {
  const calls = [];
  let failNetwork = true;
  const networkQueue = createCommandQueue({
    createRequestId: () => `rid-net-${calls.length + 1}`,
    send: async (payload) => {
      calls.push(payload);
      if (failNetwork) {
        failNetwork = false;
        throw new Error("network offline");
      }
      return { readyState: "queued", request_id: payload.request_id };
    },
  });

  await assert.rejects(
    () => networkQueue.enqueue({ command: "pause", session_id: 8, confirmed: false, mode: "fair" }),
    /network offline/,
  );
  await networkQueue.enqueue({ command: "pause", session_id: 8, confirmed: false, mode: "fair" });
  assert.equal(calls[0].request_id, calls[1].request_id);

  const definitiveCalls = [];
  const definitiveQueue = createCommandQueue({
    createRequestId: () => `rid-def-${definitiveCalls.length + 1}`,
    send: async (payload) => {
      definitiveCalls.push(payload);
      return { request_id: payload.request_id, accepted: true };
    },
    checkStatus: async (requestId) => requestId === "rid-def-1"
      ? { status: "done", response: { request_id: requestId, type: "error", code: "mic_unavailable" } }
      : { status: "done", response: { request_id: requestId, type: "state", state: "ready" } },
    pollDelayMs: 0,
    timeoutMs: 200,
  });

  await assert.rejects(
    () => definitiveQueue.enqueue({ command: "start", session_id: null, confirmed: false, mode: "fair" }),
    /mic_unavailable/,
  );
  await definitiveQueue.enqueue({ command: "start", session_id: null, confirmed: false, mode: "fair" });
  assert.notEqual(definitiveCalls[0].request_id, definitiveCalls[1].request_id);
});

test("recording and processing status navigation honors requested status index", () => {
  const first = renderTouch(touchModelForSnapshot(fixtureSnapshot("processing"), { statusIndex: 0 }));
  const second = renderTouch(touchModelForSnapshot(fixtureSnapshot("processing"), { statusIndex: 1 }));

  assert.match(first, /Captura/);
  assert.match(second, /Transcrição/);
  assert.match(second, /2 de 4/);
});

test("experience client binds subject, history and delete APIs with bearer auth", async () => {
  const calls = [];
  const client = createExperienceClient({
    tokenProvider: () => "operator-token",
    fetchImpl: async (url, init = {}) => {
      calls.push({ url: String(url), init });
      return { ok: true, status: 200, json: async () => ({ ok: true }) };
    },
  });

  await client.updateSubject(42, "biologia");
  await client.getCommandStatus("rid-1");
  await client.getSubjectHistory("biologia");
  await client.deleteSession(42);

  assert.equal(calls[0].url, "/api/v1/sessions/42/subject");
  assert.deepEqual(JSON.parse(calls[0].init.body), { subject: "biologia", confirmed: true });
  assert.equal(calls[1].url, "/api/v1/experience/commands/rid-1");
  assert.equal(calls[2].url, "/api/v1/history/subjects/biologia");
  assert.equal(calls[3].url, "/api/v1/sessions/42");
  assert.deepEqual(JSON.parse(calls[3].init.body), { confirmed: true });
  assert.equal(calls.every((call) => call.init.headers.Authorization === "Bearer operator-token"), true);
});
