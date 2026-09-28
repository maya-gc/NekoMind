import { createExperienceClient } from "./api.mjs";
import {
  automaticDiagnosticForSnapshot,
  createCommandQueue,
  fixtureSnapshot,
  routeFromPath,
  sanitizePrivateSnapshot,
  sanitizePublicSnapshot,
  touchModelForSnapshot,
} from "./state.mjs";
import {
  renderCommandState,
  renderConfirmation,
  renderHistory,
  renderPresenter,
  renderPublic,
  renderTokenPrompt as renderTokenPromptMarkup,
  renderTouch,
} from "./render.mjs?v=kitty-1";

const app = document.querySelector("#app");
const route = routeFromPath(window.location.pathname);
const params = new URLSearchParams(window.location.search);
const fixture = params.get("fixture");
const state = {
  token: "",
  snapshot: fixture ? fixtureSnapshot(fixture) : null,
  currentGeneration: null,
  draftSessionId: null,
  cardIndex: 0,
  statusIndex: 0,
  lastLocalActionAt: 0,
  pendingCommand: false,
  commandError: "",
  tokenPromptOpen: false,
  confirmation: null,
  contents: [],
  editingContentId: null,
  skipCaptureOnce: false,
  drafts: {
    tokenInput: "",
    subject: "",
    mode: "fair",
    history: null,
    contentTitle: "",
    contentText: "",
    contentPoints: "",
    contentFair: false,
    contentSource: "typed",
    contentSelection: null,
  },
};
const client = createExperienceClient({ tokenProvider: () => state.token });
const commandQueue = createCommandQueue({
  createRequestId: newRequestId,
  send: (payload) => client.enqueueCommand(payload),
  checkStatus: (requestId) => client.getCommandStatus(requestId),
  pollDelayMs: 600,
  timeoutMs: 14000,
});

render();
if (!fixture) {
  refresh();
  window.setInterval(refresh, route.view === "public" ? 2000 : 1500);
}

async function refresh() {
  try {
    const payload = route.view === "presenter" && state.token
      ? await client.getPresenter()
      : await client.getPublic();
    state.snapshot = route.view === "presenter"
      ? sanitizePrivateSnapshot(payload)
      : sanitizePublicSnapshot(payload);
    if (route.view === "presenter" && state.token) {
      try { state.contents = await client.listContents(); } catch { state.contents = []; }
    }
    render();
  } catch (error) {
    state.snapshot = sanitizePublicSnapshot({
      state: "offline",
      mode: "demo",
      diagnostics: [{ component: "backend", status: "error", message: error.message }],
      bridge_connected: false,
      error: { code: "frontend_fetch_failed", message: error.message },
    });
    render();
  }
}

function render() {
  if (state.skipCaptureOnce) state.skipCaptureOnce = false;
  else captureDrafts();
  const snapshot = state.snapshot || fixtureSnapshot("attraction");
  if (state.draftSessionId !== snapshot.session_id) {
    state.drafts.subject = "";
    state.drafts.history = null;
    state.draftSessionId = snapshot.session_id;
  }
  app.className = `app-shell view-${route.view}`;
  if (route.view === "touch") {
    const model = touchModelForSnapshot(snapshot, {
      fixture,
      emulator: true,
      currentGeneration: state.currentGeneration,
      cardIndex: state.cardIndex,
      statusIndex: state.statusIndex,
    });
    app.innerHTML = renderTouch(model);
    state.cardIndex = model.activeCard?.cardIndex || 0;
    state.currentGeneration = snapshot.generation;
  } else if (route.view === "presenter") {
    app.innerHTML = renderPresenter(snapshot, { hasToken: Boolean(state.token), contents: state.contents });
  } else {
    app.innerHTML = renderPublic(snapshot);
  }
  if (!state.tokenPromptOpen) app.insertAdjacentHTML("beforeend", renderCommandState(state));
  if (state.tokenPromptOpen) appendTokenPrompt();
  restoreDrafts();
  if (state.confirmation) {
    app.insertAdjacentHTML("beforeend", renderConfirmation(state.confirmation.label));
    app.querySelector('[data-confirm-answer="no"]')?.focus();
  }
}

app.addEventListener("click", async (event) => {
  const answer = event.target.closest("[data-confirm-answer]");
  if (answer) {
    resolveConfirmation(answer.dataset.confirmAnswer === "yes");
    return;
  }
  if (state.confirmation || state.pendingCommand) return;
  const tokenButton = event.target.closest("[data-token-submit]");
  if (tokenButton) {
    const input = app.querySelector("#presenter-token");
    const candidate = input?.value?.trim() || "";
    if (!candidate) {
      state.commandError = "Cole o token local antes de continuar.";
      state.tokenPromptOpen = true;
      render();
      return;
    }
    try {
      await client.validateOperatorToken(candidate);
    } catch (_error) {
      state.token = "";
      state.commandError = "Token local inválido. Copie o token atual e tente novamente.";
      state.tokenPromptOpen = true;
      render();
      return;
    }
    state.token = candidate;
    if (input) input.value = "";
    state.drafts.tokenInput = "";
    state.tokenPromptOpen = false;
    state.commandError = "";
    await refresh();
    const diagnostic = automaticDiagnosticForSnapshot(state.snapshot);
    if (diagnostic) {
      try {
        state.pendingCommand = true;
        render();
        await commandQueue.enqueue(diagnostic);
        state.pendingCommand = false;
        await refresh();
      } catch (error) {
        state.pendingCommand = false;
        state.commandError = `Token aceito. O diagnóstico automático falhou: ${error.message || "tente novamente"}`;
        render();
      }
    }
    return;
  }

  const subjectButton = event.target.closest("[data-subject-submit]");
  if (subjectButton) {
    await submitSubject();
    return;
  }

  const contentAction = event.target.closest("[data-content-select],[data-content-new],[data-content-edit],[data-content-save],[data-content-delete]");
  if (contentAction && route.view === "presenter") {
    await handleContentAction(contentAction);
    return;
  }

  const historyButton = event.target.closest("[data-subject-history]");
  if (historyButton) {
    await loadSubjectHistory();
    return;
  }

  const deleteButton = event.target.closest("[data-session-delete]");
  if (deleteButton) {
    await deleteCurrentSession(deleteButton);
    return;
  }

  const local = event.target.closest("[data-local-action]");
  if (local) {
    const now = performance.now();
    if (now - state.lastLocalActionAt < 280) return;
    state.lastLocalActionAt = now;
    const cards = state.snapshot ? touchModelForSnapshot(state.snapshot, state).cards : [];
    if (local.dataset.localAction === "next-card") state.cardIndex = Math.min(state.cardIndex + 1, Math.max(cards.length - 1, 0));
    if (local.dataset.localAction === "prev-card") state.cardIndex = Math.max(state.cardIndex - 1, 0);
    if (local.dataset.localAction === "next-status") state.statusIndex += 1;
    if (local.dataset.localAction === "prev-status") state.statusIndex = Math.max(state.statusIndex - 1, 0);
    render();
    return;
  }

  const button = event.target.closest("[data-command]");
  if (!button || !button.dataset.command) return;
  const command = button.dataset.command;
  if (!state.token) {
    renderTokenPrompt();
    return;
  }
  const mustConfirm = button.dataset.confirmed === "true";
  const sessionId = state.snapshot?.session_id ?? null;
  if (mustConfirm && !await confirmAction(`Confirmar ${button.textContent.trim()}?`)) return;
  if (sessionId !== (state.snapshot?.session_id ?? null)) return;
  try {
    state.pendingCommand = true;
    state.commandError = "";
    render();
    await commandQueue.enqueue({
      command,
      session_id: command === "start" ? null : sessionId,
      confirmed: mustConfirm,
      mode: state.drafts.mode || state.snapshot?.experience_mode || "fair",
    });
    state.pendingCommand = false;
    state.commandError = "";
    await refresh();
  } catch (error) {
    state.pendingCommand = false;
    state.commandError = error.message || "Falha ao enviar comando. Toque novamente para reenviar.";
    render();
  }
});

app.addEventListener("change", async (event) => {
  const file = event.target.matches("[data-content-file]") ? event.target.files?.[0] : null;
  if (!file) return;
  if (!/\.(txt|md)$/i.test(file.name) || file.size > 50000) {
    state.commandError = "Use um arquivo .txt ou .md com até 50 KB.";
    render();
    return;
  }
  state.drafts.contentText = await file.text();
  state.drafts.contentSource = file.name.toLowerCase().endsWith(".md") ? "md" : "txt";
  if (!state.drafts.contentTitle) state.drafts.contentTitle = file.name.replace(/\.(txt|md)$/i, "");
  state.skipCaptureOnce = true;
  render();
});

async function handleContentAction(button) {
  if (!state.token) return renderTokenPrompt();
  captureDrafts();
  const selected = Number(app.querySelector("[data-content-selection]")?.value) || null;
  try {
    if (button.hasAttribute("data-content-new")) {
      state.editingContentId = null;
      Object.assign(state.drafts, { contentTitle: "", contentText: "", contentPoints: "", contentFair: false, contentSource: "typed" });
    } else if (button.hasAttribute("data-content-select")) {
      await client.selectContent(selected);
      state.drafts.contentSelection = null;
      state.skipCaptureOnce = true;
      await refresh();
      return;
    } else if (button.hasAttribute("data-content-edit")) {
      if (!selected) throw new Error("Escolha um conteúdo para editar.");
      const item = await client.getContent(selected);
      state.editingContentId = selected;
      Object.assign(state.drafts, { contentTitle: item.title, contentText: item.text,
        contentPoints: item.points.join("\n"), contentFair: item.fair_available, contentSource: item.source });
    } else if (button.hasAttribute("data-content-save")) {
      const d = state.drafts;
      await client.saveContent(state.editingContentId, { title: d.contentTitle.trim(), text: d.contentText.trim(),
        source: d.contentSource, fair_available: d.contentFair,
        points: d.contentPoints.trim() ? d.contentPoints.split("\n").map((s) => s.trim()).filter(Boolean) : null });
      state.editingContentId = null;
      await refresh();
      return;
    } else if (button.hasAttribute("data-content-delete")) {
      if (!selected || !await confirmAction("Excluir o conteúdo selecionado? Sessões antigas mantêm uma cópia local da versão usada.")) return;
      await client.deleteContent(selected);
      if (state.snapshot?.selected_content_id === selected) await client.selectContent(null);
      state.drafts.contentSelection = null;
      state.skipCaptureOnce = true;
      await refresh();
      return;
    }
    state.commandError = "";
  } catch (error) {
    state.commandError = error.message || "Falha ao atualizar conteúdo.";
  }
  state.skipCaptureOnce = true;
  render();
}

function confirmAction(label) {
  return new Promise((resolve) => {
    state.confirmation = { label, resolve };
    render();
  });
}

function resolveConfirmation(accepted) {
  const pending = state.confirmation;
  state.confirmation = null;
  render();
  pending?.resolve(accepted);
}

app.addEventListener("keydown", (event) => {
  if (!state.confirmation) return;
  if (event.key === "Escape") {
    event.preventDefault();
    resolveConfirmation(false);
  } else if (event.key === "Tab") {
    event.preventDefault();
    const buttons = [...app.querySelectorAll("[data-confirm-answer]")];
    buttons[(buttons.indexOf(document.activeElement) + 1) % buttons.length]?.focus();
  }
});

function renderTokenPrompt() {
  state.tokenPromptOpen = true;
  appendTokenPrompt();
}

function appendTokenPrompt() {
  if (app.querySelector(".token-modal")) return;
  const panel = document.createElement("section");
  panel.className = "token-modal";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Token local do emulador");
  panel.innerHTML = renderTokenPromptMarkup({
    commandError: state.commandError,
    tokenInput: state.drafts.tokenInput,
  });
  app.append(panel);
  panel.querySelector("input")?.focus();
}

app.addEventListener("click", (event) => {
  if (!event.target.closest("[data-token-close]")) return;
  state.tokenPromptOpen = false;
  event.target.closest(".token-modal")?.remove();
});

app.addEventListener("input", (event) => {
  if (event.target.matches("#presenter-token")) state.drafts.tokenInput = event.target.value;
  if (event.target.matches("[data-subject-input]")) state.drafts.subject = event.target.value;
  if (event.target.matches("[data-experience-mode]")) state.drafts.mode = event.target.value;
});

async function submitSubject() {
  if (!state.snapshot?.session_id || !state.token) return renderTokenPrompt();
  try {
    const subject = app.querySelector("[data-subject-input]")?.value?.trim() || "";
    await client.updateSubject(state.snapshot.session_id, subject);
    state.drafts.subject = subject;
    state.commandError = "";
    await refresh();
  } catch (error) {
    state.commandError = error.message || "Falha ao confirmar assunto";
    render();
  }
}

async function loadSubjectHistory() {
  if (!state.token) return renderTokenPrompt();
  try {
    const subject = app.querySelector("[data-subject-input]")?.value?.trim() || state.snapshot?.result?.subject || "";
    const history = await client.getSubjectHistory(subject);
    state.drafts.history = history;
    render();
  } catch (error) {
    state.commandError = error.message || "Falha ao carregar histórico";
    render();
  }
}

async function deleteCurrentSession(button) {
  if (!state.snapshot?.session_id || !state.token) return renderTokenPrompt();
  const sessionId = state.snapshot.session_id;
  if (button.dataset.confirmed === "true" && !await confirmAction("Excluir esta sessão e seus dados locais?")) return;
  if (sessionId !== state.snapshot?.session_id) return;
  try {
    await client.deleteSession(sessionId);
    state.drafts.history = null;
    state.drafts.subject = "";
    state.commandError = "";
    await refresh();
  } catch (error) {
    state.commandError = error.message || "Falha ao excluir sessão";
    render();
  }
}

function captureDrafts() {
  const tokenInput = app.querySelector("#presenter-token");
  const subjectInput = app.querySelector("[data-subject-input]");
  const modeSelect = app.querySelector("[data-experience-mode]");
  if (tokenInput) state.drafts.tokenInput = tokenInput.value;
  if (subjectInput) state.drafts.subject = subjectInput.value;
  if (modeSelect) state.drafts.mode = modeSelect.value;
  for (const [key, selector] of [["contentTitle", "[data-content-title]"], ["contentText", "[data-content-text]"], ["contentPoints", "[data-content-points]"]]) {
    const input = app.querySelector(selector);
    if (input) state.drafts[key] = input.value;
  }
  const fair = app.querySelector("[data-content-fair]");
  if (fair) state.drafts.contentFair = fair.checked;
  const selection = app.querySelector("[data-content-selection]");
  if (selection) state.drafts.contentSelection = selection.value;
}

function restoreDrafts() {
  const tokenInput = app.querySelector("#presenter-token");
  const subjectInput = app.querySelector("[data-subject-input]");
  const modeSelect = app.querySelector("[data-experience-mode]");
  const historyPanel = app.querySelector("[data-history-panel]");
  if (tokenInput) tokenInput.value = state.drafts.tokenInput;
  if (subjectInput && state.drafts.subject) subjectInput.value = state.drafts.subject;
  if (modeSelect) modeSelect.value = state.drafts.mode;
  if (historyPanel && state.drafts.history) historyPanel.innerHTML = renderHistory(state.drafts.history);
  for (const [key, selector] of [["contentTitle", "[data-content-title]"], ["contentText", "[data-content-text]"], ["contentPoints", "[data-content-points]"]]) {
    const input = app.querySelector(selector);
    if (input) input.value = state.drafts[key];
  }
  const fair = app.querySelector("[data-content-fair]");
  if (fair) fair.checked = state.drafts.contentFair;
  const selection = app.querySelector("[data-content-selection]");
  if (selection && state.drafts.contentSelection !== null) selection.value = state.drafts.contentSelection;
}

function newRequestId() {
  return globalThis.crypto?.randomUUID?.() || `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
