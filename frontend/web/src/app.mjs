import { createExperienceClient } from "./api.mjs?v=briefing-3";
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
} from "./render.mjs?v=briefing-4";
import { captureTextareaScroll, restoreTextareaScroll } from "./scroll_state.mjs";
import { shouldDeferPresenterRefresh } from "./presenter_refresh.mjs";

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
  pendingBriefing: false,
  filePickerOpen: false,
  commandError: "",
  tokenPromptOpen: false,
  confirmation: null,
  contents: [],
  contentNotice: "",
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
    contentUrl: "",
    contentSelection: null,
    libraryOpen: false,
    advancedOpen: false,
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
    if (route.view === "presenter" && shouldDeferPresenterRefresh(app, document.activeElement, state.filePickerOpen)) {
      captureDrafts();
      return;
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
    if (route.view === "presenter" && shouldDeferPresenterRefresh(app, document.activeElement, state.filePickerOpen)) {
      captureDrafts();
      return;
    }
    render();
  }
}

function render() {
  const textareaScroll = route.view === "presenter" ? captureTextareaScroll(app) : [];
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
    app.innerHTML = renderPresenter(snapshot, { hasToken: Boolean(state.token), contents: state.contents, contentNotice: state.contentNotice, authError: !state.token ? state.commandError : "" });
  } else {
    app.innerHTML = renderPublic(snapshot);
  }
  if (!state.tokenPromptOpen && !(route.view === "presenter" && !state.token)) app.insertAdjacentHTML("beforeend", renderCommandState(state));
  if (state.tokenPromptOpen) appendTokenPrompt();
  restoreDrafts();
  if (route.view === "presenter") restoreTextareaScroll(app, textareaScroll);
  if (state.confirmation) {
    app.insertAdjacentHTML("beforeend", renderConfirmation(state.confirmation.label));
    app.querySelector('[data-confirm-answer="no"]')?.focus();
  }
}

app.addEventListener("click", async (event) => {
  // The native file dialog may outlive several polling intervals. Keep its
  // input mounted so Safari can deliver the selected file's change event.
  if (event.target.closest(".upload-field")) state.filePickerOpen = true;
  const answer = event.target.closest("[data-confirm-answer]");
  if (answer) {
    resolveConfirmation(answer.dataset.confirmAnswer === "yes");
    return;
  }
  if (state.confirmation || state.pendingCommand || state.pendingBriefing) return;
  const tokenButton = event.target.closest("[data-token-submit]");
  if (tokenButton) {
    const input = app.querySelector("#presenter-token");
    const candidate = input?.value?.trim() || "";
    if (!candidate) {
      state.commandError = "Cole o token local antes de continuar.";
      render();
      app.querySelector("#presenter-token")?.focus();
      return;
    }
    try {
      await client.validateOperatorToken(candidate);
    } catch (_error) {
      state.token = "";
      state.commandError = "Token local inválido. Copie o token atual e tente novamente.";
      render();
      app.querySelector("#presenter-token")?.focus();
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

  const contentAction = event.target.closest("[data-content-select],[data-content-new],[data-content-edit],[data-content-save],[data-content-save-and-select],[data-content-delete],[data-content-import-url],[data-content-analyze]");
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
  const isFileInput = event.target.matches("[data-content-file]");
  if (isFileInput) state.filePickerOpen = false;
  const file = isFileInput ? event.target.files?.[0] : null;
  if (!file) return;
  if (/\.pdf$/i.test(file.name)) {
    if (file.size > 5 * 1024 * 1024) {
      state.contentNotice = "Use um PDF com até 5 MB.";
      state.commandError = "";
      render();
      return;
    }
    let loaded = false;
    try {
      state.contentNotice = "Lendo PDF localmente...";
      render();
      const preview = await client.importPdf(file);
      state.editingContentId = null;
      state.drafts.contentTitle = file.name.replace(/\.pdf$/i, "").slice(0, 200);
      state.drafts.contentText = preview.text;
      state.drafts.contentPoints = preview.points.join("\n");
      state.drafts.contentSource = "pdf";
      loaded = true;
      state.commandError = "";
      await runLocalAnalysis(preview.text);
      state.contentNotice = `PDF lido (${preview.page_count} página(s)) e analisado pela IA local. Revise os pontos antes de usar.`;
      state.skipCaptureOnce = true;
      render();
    } catch (error) {
      state.contentNotice = loaded
        ? `PDF carregado, mas a análise local falhou: ${error.message || "tente novamente"}`
        : `Não foi possível ler o PDF: ${error.message || "tente outro arquivo"}`;
      state.commandError = "";
      state.skipCaptureOnce = true;
      render();
    }
    return;
  }
  if (!/\.(txt|md)$/i.test(file.name) || file.size > 50000) {
    state.contentNotice = "Use PDF, .txt ou .md dentro dos limites indicados.";
    state.commandError = "";
    render();
    return;
  }
  try {
    state.drafts.contentText = await file.text();
    state.drafts.contentSource = file.name.toLowerCase().endsWith(".md") ? "md" : "txt";
    state.editingContentId = null;
    state.drafts.contentTitle = file.name.replace(/\.(txt|md)$/i, "").slice(0, 200);
    await runLocalAnalysis(state.drafts.contentText);
  } catch (error) {
    state.commandError = error.message || "Falha ao analisar arquivo.";
    state.contentNotice = "Arquivo carregado. Confira o texto e tente analisar novamente.";
  }
  state.skipCaptureOnce = true;
  render();
});

app.addEventListener("cancel", (event) => {
  if (event.target.matches("[data-content-file]")) state.filePickerOpen = false;
}, true);

window.addEventListener("focus", () => {
  if (state.filePickerOpen) window.setTimeout(() => { state.filePickerOpen = false; }, 700);
});

async function runLocalAnalysis(text) {
  state.pendingBriefing = true;
  state.drafts.contentPoints = "";
  state.contentNotice = "A IA local está escolhendo trechos do material...";
  state.skipCaptureOnce = true;
  render();
  try {
    const preview = await client.analyzeBriefing(text);
    state.drafts.contentPoints = preview.points.join("\n");
    state.contentNotice = preview.sampled
      ? `Análise local concluída (${preview.model}) com trechos distribuídos pelo texto. Confira os pontos antes de usar.`
      : `Análise local concluída (${preview.model}). Confira os pontos antes de usar.`;
    state.commandError = "";
  } finally {
    state.pendingBriefing = false;
  }
}

async function handleContentAction(button) {
  if (!state.token) return renderTokenPrompt();
  captureDrafts();
  const selected = Number(app.querySelector("[data-content-selection]")?.value) || null;
  let savedDuringAction = false;
  let importedDuringAction = false;
  try {
    if (button.hasAttribute("data-content-import-url")) {
      const input = state.drafts.contentUrl.trim();
      const url = /^https?:\/\//i.test(input) ? input : `https://${input}`;
      if (!input) throw new Error("Cole o link de uma página antes de carregar.");
      const preview = await client.importUrl(url);
      state.editingContentId = null;
      Object.assign(state.drafts, { contentTitle: preview.title, contentText: preview.text,
        contentPoints: preview.points.join("\n"), contentSource: "url" });
      importedDuringAction = true;
      await runLocalAnalysis(preview.text);
      state.contentNotice = "Página carregada e analisada pela IA local. Confira os pontos antes de usar.";
    } else if (button.hasAttribute("data-content-analyze")) {
      const text = state.drafts.contentText.trim();
      if (!text) throw new Error("Cole um texto ou carregue um PDF/site antes de analisar.");
      await runLocalAnalysis(text);
    } else if (button.hasAttribute("data-content-new")) {
      state.editingContentId = null;
      state.contentNotice = "";
      Object.assign(state.drafts, { contentTitle: "", contentText: "", contentPoints: "", contentUrl: "", contentFair: false, contentSource: "typed" });
    } else if (button.hasAttribute("data-content-select")) {
      await client.selectContent(selected);
      state.drafts.contentSelection = null;
      state.contentNotice = selected ? "Conteúdo aplicado à próxima sessão." : "Modo livre aplicado à próxima sessão.";
      state.skipCaptureOnce = true;
      await refresh();
      return;
    } else if (button.hasAttribute("data-content-edit")) {
      if (!selected) throw new Error("Escolha um conteúdo para editar.");
      const item = await client.getContent(selected);
      state.editingContentId = selected;
      state.contentNotice = "Editando conteúdo selecionado.";
      Object.assign(state.drafts, { contentTitle: item.title, contentText: item.text,
        contentPoints: item.points.join("\n"), contentFair: item.fair_available, contentSource: item.source });
    } else if (button.hasAttribute("data-content-save") || button.hasAttribute("data-content-save-and-select")) {
      const d = state.drafts;
      if (!d.contentPoints.trim()) throw new Error("Prepare e confira ao menos um ponto antes de usar.");
      const saved = await client.saveContent(state.editingContentId, { title: d.contentTitle.trim(), text: d.contentText.trim(),
        source: d.contentSource, fair_available: d.contentFair,
        points: d.contentPoints.trim() ? d.contentPoints.split("\n").map((s) => s.trim()).filter(Boolean) : null });
      savedDuringAction = true;
      state.editingContentId = saved.id;
      if (button.hasAttribute("data-content-save-and-select")) {
        state.contentNotice = "Conteúdo salvo. Aplicando à próxima sessão...";
        await client.selectContent(saved.id);
      }
      state.editingContentId = null;
      Object.assign(state.drafts, { contentTitle: "", contentText: "", contentPoints: "", contentFair: false, contentSource: "typed", contentSelection: String(saved.id) });
      state.contentNotice = button.hasAttribute("data-content-save-and-select")
        ? `Pronto! ${saved.title} será usado na próxima sessão. Comece pelo display.`
        : `Conteúdo salvo · v${saved.version}. Escolha-o na biblioteca para usar.`;
      state.skipCaptureOnce = true;
      await refresh();
      return;
    } else if (button.hasAttribute("data-content-delete")) {
      if (!selected || !await confirmAction("Excluir o conteúdo selecionado? Sessões antigas mantêm uma cópia local da versão usada.")) return;
      await client.deleteContent(selected);
      if (state.snapshot?.selected_content_id === selected) await client.selectContent(null);
      state.drafts.contentSelection = null;
      state.contentNotice = "Conteúdo excluído da biblioteca.";
      state.skipCaptureOnce = true;
      await refresh();
      return;
    }
    state.commandError = "";
  } catch (error) {
    state.commandError = error.message || "Falha ao atualizar conteúdo.";
    if (button.hasAttribute("data-content-analyze")) state.contentNotice = "";
    if (button.hasAttribute("data-content-import-url") && importedDuringAction) {
      state.contentNotice = `Página carregada, mas a análise local falhou: ${state.commandError}`;
      state.commandError = "";
    }
    if (button.hasAttribute("data-content-save-and-select") && savedDuringAction) {
      state.contentNotice = "O briefing foi salvo, mas não aplicado. Tente novamente ao fim da sessão.";
    }
  }
  state.pendingBriefing = false;
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
  for (const [key, selector] of [["contentTitle", "[data-content-title]"], ["contentText", "[data-content-text]"], ["contentPoints", "[data-content-points]"], ["contentUrl", "[data-content-url]"]]) {
    const input = app.querySelector(selector);
    if (input) state.drafts[key] = input.value;
  }
  const fair = app.querySelector("[data-content-fair]");
  if (fair) state.drafts.contentFair = fair.checked;
  const selection = app.querySelector("[data-content-selection]");
  if (selection) state.drafts.contentSelection = selection.value;
  state.drafts.libraryOpen = Boolean(app.querySelector("[data-presenter-library]")?.open);
  state.drafts.advancedOpen = Boolean(app.querySelector("[data-presenter-advanced]")?.open);
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
  for (const [key, selector] of [["contentTitle", "[data-content-title]"], ["contentText", "[data-content-text]"], ["contentPoints", "[data-content-points]"], ["contentUrl", "[data-content-url]"]]) {
    const input = app.querySelector(selector);
    if (input) input.value = state.drafts[key];
  }
  const fair = app.querySelector("[data-content-fair]");
  if (fair) fair.checked = state.drafts.contentFair;
  const selection = app.querySelector("[data-content-selection]");
  if (selection && state.drafts.contentSelection !== null) selection.value = state.drafts.contentSelection;
  const library = app.querySelector("[data-presenter-library]");
  if (library) library.open = state.drafts.libraryOpen;
  const advanced = app.querySelector("[data-presenter-advanced]");
  if (advanced) advanced.open = state.drafts.advancedOpen;
}

function newRequestId() {
  return globalThis.crypto?.randomUUID?.() || `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
