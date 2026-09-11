import { statusLabel, stepLabel } from "./state.mjs";

export function renderConfirmation(label) {
  return `<section class="confirmation-modal" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title">
    <div><h2 id="confirm-title">${escapeHtml(label)}</h2>
      <button type="button" data-confirm-answer="yes">Confirmar</button>
      <button type="button" data-confirm-answer="no">Voltar</button>
    </div>
  </section>`;
}

export function renderTokenPrompt({ commandError = "", tokenInput = "" } = {}) {
  const error = commandError
    ? `<p class="token-error" role="alert">${escapeHtml(commandError)}</p>`
    : "";
  return `<div>
      <h2>Token local</h2>
      <p>Usado só nesta página para autorizar comandos do emulador.</p>
      <input id="presenter-token" type="password" autocomplete="off" placeholder="colar token" value="${escapeAttr(tokenInput)}" />
      ${error}
      <div class="token-actions">
        <button type="button" data-token-submit>Usar token</button>
        <button type="button" data-token-close>Agora não</button>
      </div>
    </div>`;
}

export function renderTouch(model) {
  const active = model.activeCard?.card;
  const isResult = Boolean(active);
  return `
    <section class="touch-frame state-${escapeAttr(model.state)}" data-view="touch">
      <header class="touch-top">
        ${model.badges.map(renderBadge).join("")}
      </header>
      <div class="touch-main ${isResult ? "is-result" : ""}">
        ${renderCatFace({ state: model.state, voice: model.voice, compact: isResult })}
        <section class="touch-copy">
          <h1>${escapeHtml(isResult ? active.label : model.title)}</h1>
          <p>${escapeHtml(isResult ? active.value : model.detail)}</p>
        </section>
        ${isResult ? renderCardNav(model) : renderTouchStatus(model)}
      </div>
      <footer class="touch-actions">
        ${renderAction(model.primaryAction, "primary")}
        ${model.secondaryActions.map((action) => renderAction(action, "secondary")).join("")}
      </footer>
    </section>`;
}

export function renderPublic(snapshot) {
  return `
    <section class="public-stage state-${escapeAttr(snapshot.state)}" data-view="public">
      <header class="public-header">
        <span class="mode-pill mode-${escapeAttr(snapshot.mode)}">${escapeHtml(snapshot.mode === "real" ? "REAL" : "DEMO")}</span>
        ${snapshot.fixture_label ? `<span class="fixture-pill">${escapeHtml(snapshot.fixture_label)}</span>` : ""}
        <span>${escapeHtml(snapshot.bridge_connected ? "ponte conectada" : "ponte offline")}</span>
      </header>
      <div class="public-layout">
        <div class="public-face">
          ${renderCatFace({ state: snapshot.state, voice: snapshot.voice })}
          <h1>${escapeHtml(publicTitle(snapshot))}</h1>
          <p>${escapeHtml(publicSubtitle(snapshot))}</p>
        </div>
        <aside class="journey-panel" aria-label="Jornada da sessão">
          <h2>Jornada da sessão</h2>
          ${renderJourney(snapshot.journey)}
        </aside>
      </div>
      <section class="public-result" aria-label="Resultado público">
        ${renderPublicResult(snapshot)}
      </section>
    </section>`;
}

export function renderPresenter(snapshot, options = {}) {
  const tokenState = options.hasToken ? "token em memória" : "informe token local";
  return `
    <section class="presenter-console state-${escapeAttr(snapshot.state)}" data-view="presenter">
      <header class="presenter-header">
        <div>
          <h1>NekoMind operador</h1>
          <p>${escapeHtml(tokenState)} · sessão ${escapeHtml(snapshot.session_id ?? "nenhuma")}</p>
        </div>
        ${snapshot.fixture_label ? `<span class="fixture-pill">${escapeHtml(snapshot.fixture_label)}</span>` : ""}
      </header>
      <section class="token-panel" data-token-state="${options.hasToken ? "ready" : "missing"}">
        <label for="presenter-token">Token local</label>
        <input id="presenter-token" name="presenter-token" type="password" autocomplete="off" placeholder="colar token do operador" />
        <button type="button" data-token-submit>Usar token</button>
      </section>
      <div class="presenter-grid">
        <section class="ops-panel">
          <h2>Prontidão</h2>
          ${renderDiagnostics(snapshot.diagnostics)}
        </section>
        <section class="ops-panel">
          <h2>Sessão atual</h2>
          <label class="field-row">Modo
            <select name="experience-mode" data-experience-mode>
              <option value="fair" ${snapshot.experience_mode === "fair" ? "selected" : ""}>Feira</option>
              <option value="normal" ${snapshot.experience_mode === "normal" ? "selected" : ""}>Normal</option>
            </select>
          </label>
          ${renderJourney(snapshot.journey)}
          ${snapshot.error ? `<p class="safe-error">${escapeHtml(snapshot.error.code)}: ${escapeHtml(snapshot.error.message)}</p>` : ""}
          ${options.hasToken ? renderRecoverable(snapshot.recoverable_sessions) : '<p class="empty-result">Informe o token para consultar recuperações.</p>'}
        </section>
        <section class="ops-panel">
          <h2>Assunto e histórico</h2>
          <label class="field-row">Assunto confirmado
            <input name="subject" data-subject-input value="${escapeAttr(snapshot.result?.subject || "")}" placeholder="ex.: biologia" />
          </label>
          <div class="button-stack">
            <button type="button" data-subject-submit>Confirmar assunto</button>
            <button type="button" data-subject-submit data-correct="true">Corrigir assunto</button>
            <button type="button" data-subject-history>Histórico</button>
            <button type="button" data-session-delete data-confirmed="true">Excluir sessão</button>
          </div>
          <div class="history-panel" data-history-panel></div>
        </section>
        <section class="ops-panel danger-zone">
          <h2>Ações seguras</h2>
          <p>Você confirma antes de cancelar, descartar ou reiniciar.</p>
          <div class="button-stack">
            ${renderPresenterButton("diagnose", "Diagnóstico", false)}
            ${renderPresenterButton("calibrate", "Calibrar", false)}
            ${renderPresenterButton("result", "Ver resultado", false)}
            ${renderPresenterButton("cancel", "Cancelar sessão", true)}
            ${renderPresenterButton("recover", "Recuperar sessão", true)}
            ${renderPresenterButton("discard", "Descartar recuperação", true)}
            ${renderPresenterButton("reset", "Reset feira", true)}
          </div>
        </section>
      </div>
    </section>`;
}

export function renderCommandState({ pendingCommand = false, commandError = "" } = {}) {
  if (!pendingCommand && !commandError) return "";
  return `<div class="command-state" role="status">${escapeHtml(pendingCommand ? "Comando enviado; aguardando Mac..." : commandError)}</div>`;
}

export function renderHistory(history = {}) {
  const points = Array.isArray(history.points) ? history.points : Array.isArray(history.sessions) ? history.sessions : [];
  const rows = points.map((point) => {
    const session = point.session_id ?? point.id ?? "-";
    const when = formatDate(point.ended_at || point.created_at || point.completed_at || point.date);
    const duration = Number.isFinite(Number(point.duration_seconds)) ? `${Number(point.duration_seconds)}s` : "sem duração";
    const clarity = Number.isFinite(Number(point.clarity_score)) ? Number(point.clarity_score).toFixed(2) : "sem clareza";
    const topics = Array.isArray(point.topics) ? point.topics.slice(0, 3).map(escapeHtml).join(", ") : "sem tópicos";
    const method = escapeHtml(point.metric_method_version || point.method_version || history.method_version || "");
    return `<li>
      <strong>S${escapeHtml(session)}</strong>
      <span>${escapeHtml(when)}</span>
      <span>${escapeHtml(duration)} · clareza ${escapeHtml(clarity)}</span>
      <small>${topics}${method ? ` · método ${method}` : ""}</small>
    </li>`;
  }).join("");
  const trend = renderHistoryTrend(history);
  const disclaimer = history.disclaimer ? `<p class="history-disclaimer">${escapeHtml(history.disclaimer)}</p>` : "";
  return `<section class="history-result" aria-label="Histórico do assunto">
    ${rows ? `<ul>${rows}</ul>` : `<p class="empty-result">Sem histórico confirmado para este assunto.</p>`}
    ${trend}
    ${disclaimer}
  </section>`;
}

export function renderCatFace({ state = "idle", voice = null, compact = false } = {}) {
  const level = voice?.level ?? 0;
  const clipping = voice?.clipping || voice?.quality === "clipping";
  const low = voice?.quality === "low";
  const eyeY = state === "paused" ? 73 : state === "error" ? 79 : 70;
  const mouth = state === "completed" ? "M96 121 Q120 139 144 121" : state === "error" ? "M102 130 Q120 120 138 130" : "M106 122 Q120 130 134 122";
  return `
    <svg class="cat-face ${compact ? "is-compact" : ""} ${clipping ? "is-clipping" : ""} ${low ? "is-low" : ""}"
      data-state="${escapeAttr(state)}"
      viewBox="0 0 240 180"
      role="img"
      aria-label="Rosto-instrumento NekoMind em estado ${escapeAttr(state)}">
      <title>Rosto-instrumento NekoMind</title>
      <path class="cat-ear" d="M55 54 L74 12 L94 62 Z" />
      <path class="cat-ear right" d="M145 62 L166 12 L186 54 Z" />
      <path class="cat-head" d="M50 73 C50 35 190 35 190 73 L190 118 C190 155 50 155 50 118 Z" />
      <circle class="cat-eye" cx="91" cy="${eyeY}" r="14" />
      <circle class="cat-eye" cx="149" cy="${eyeY}" r="14" />
      <circle class="cat-pupil" cx="${state === "processing" ? 96 : 91}" cy="${eyeY}" r="5" />
      <circle class="cat-pupil" cx="${state === "processing" ? 154 : 149}" cy="${eyeY}" r="5" />
      <path class="cat-nose" d="M113 102 L127 102 L120 111 Z" />
      <path class="cat-mouth" d="${mouth}" />
      <path class="cat-whisker left" style="--voice:${level}" d="M108 112 L50 102 M108 120 L43 120 M108 128 L50 139" />
      <path class="cat-whisker right" style="--voice:${level}" d="M132 112 L190 102 M132 120 L197 120 M132 128 L190 139" />
      <circle class="voice-dot" cx="120" cy="151" r="${Math.max(5, Math.min(18, 5 + level / 7))}" />
    </svg>`;
}

function renderTouchStatus(model) {
  if (model.activeStatus) {
    return `<section class="touch-status-card" data-status="${escapeAttr(model.activeStatus.status)}">
      <strong>${escapeHtml(model.activeStatus.title)}</strong>
      <span>${escapeHtml(model.activeStatus.status)}</span>
      <small>${escapeHtml(model.activeStatus.detail)}</small>
      ${model.activeStatus.total > 1 ? `<nav class="mini-nav" aria-label="Status anterior e próximo">
        <button type="button" data-local-action="prev-status" aria-label="Status anterior">‹</button>
        <em>${model.activeStatus.index + 1} de ${model.activeStatus.total}</em>
        <button type="button" data-local-action="next-status" aria-label="Próximo status">›</button>
      </nav>` : ""}
    </section>`;
  }
  if (model.error) return `<p class="safe-error">${escapeHtml(model.error.message)}</p>`;
  return "";
}

function renderPublicResult(snapshot) {
  if (!snapshot.result) {
    return `<p class="empty-result">Sem dados do visitante anterior.</p>`;
  }
  const topics = snapshot.result.topics.map((topic) => `<li>${escapeHtml(topic)}</li>`).join("");
  return `<ul class="topic-strip">${topics}</ul>`;
}

function renderJourney(journey = []) {
  return `<ol class="journey-list">${journey.map((step) => `
    <li data-status="${escapeAttr(step.status)}">
      <span>${escapeHtml(stepLabel(step.step))}</span>
      <strong>${escapeHtml(statusLabel(step.status))}</strong>
      <small>${escapeHtml(step.provider || "sem provedor")} ${step.is_demo ? "· demo" : ""}${step.duration_ms === null ? "" : ` · ${step.duration_ms}ms`}</small>
    </li>`).join("")}</ol>`;
}

function renderDiagnostics(items = []) {
  return `<ul class="diagnostic-list">${items.map((item) => `
    <li data-status="${escapeAttr(item.status)}">
      <strong>${escapeHtml(item.component)}</strong>
      <span>${escapeHtml(statusLabel(item.status))}</span>
      <small>${escapeHtml(item.message)}</small>
    </li>`).join("")}</ul>`;
}

function renderRecoverable(items = []) {
  if (!Array.isArray(items) || !items.length) return `<p class="empty-result">Sem recuperação pendente.</p>`;
  return `<ul class="recoverable-list">${items.map((item) => `<li>S${escapeHtml(item.session_id)} · ${escapeHtml(item.subject || "sem assunto")} · ${escapeHtml(item.state)}</li>`).join("")}</ul>`;
}

function renderHistoryTrend(history) {
  const trend = history.trend && typeof history.trend === "object" ? history.trend : null;
  if (!trend) return "";
  const bits = [];
  if (Number.isFinite(Number(trend.duration_seconds_delta))) bits.push(`duração ${formatSigned(trend.duration_seconds_delta)}s`);
  if (Number.isFinite(Number(trend.clarity_score_delta))) bits.push(`clareza ${formatSigned(trend.clarity_score_delta)}`);
  if (Number.isFinite(Number(trend.topic_count_delta))) bits.push(`tópicos ${formatSigned(trend.topic_count_delta)}`);
  return bits.length ? `<p class="history-trend">${escapeHtml(bits.join(" · "))}</p>` : "";
}

function formatDate(value) {
  if (!value) return "sem data";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function formatSigned(value) {
  const number = Number(value);
  return number > 0 ? `+${number}` : String(number);
}

function renderCardNav(model) {
  return `<nav class="card-nav" aria-label="Navegação dos cartões">
    <button type="button" data-local-action="prev-card" aria-label="Cartão anterior">‹</button>
    <span>${model.activeCard.cardIndex + 1}/${model.activeCard.total}</span>
    <button type="button" data-local-action="next-card" aria-label="Próximo cartão">›</button>
  </nav>`;
}

function renderPresenterButton(command, label, confirmed) {
  return `<button type="button" data-command="${escapeAttr(command)}" data-confirmed="${confirmed ? "true" : "false"}">${escapeHtml(label)}</button>`;
}

function renderAction(action, tone) {
  const disabled = action.disabled || !action.command;
  return `<button type="button"
    class="${tone}-action"
    ${action.localOnly ? `data-local-action="${escapeAttr(action.command || "")}"` : `data-command="${escapeAttr(action.command || "")}"`}
    data-confirmed="${action.confirmed ? "true" : "false"}"
    ${disabled ? "disabled" : ""}
    aria-label="${escapeAttr(action.label)}">${escapeHtml(action.label)}</button>`;
}

function renderBadge(badge) {
  return `<span class="status-badge tone-${escapeAttr(badge.tone)}" title="${escapeAttr(badge.title || badge.text)}">${escapeHtml(badge.text)}</span>`;
}

function publicTitle(snapshot) {
  if (snapshot.error) return snapshot.error.message;
  if (snapshot.result) return snapshot.result.subject || "Resultado NekoMind";
  if (snapshot.state === "recording") return "Explicação em andamento";
  if (snapshot.state === "processing") return "Análise em andamento";
  if (snapshot.state === "recovery") return "Aguardando operador";
  return "Toque no display para explicar";
}

function publicSubtitle(snapshot) {
  if (snapshot.result) return snapshot.result.summary;
  if (snapshot.state === "processing") return "A resposta muda quando a bancada confirma cada etapa.";
  if (snapshot.state === "recording") return "Áudio fica no Mac; esta tela não usa microfone.";
  return "A tela pública é somente leitura.";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("`", "&#96;");
}
