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
          ${isResult ? renderTouchResultCard(active, model) : `<p>${escapeHtml(model.detail)}</p>`}
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
  const eyes = state === "paused"
    ? `<path class="cat-eye-closed" d="M82 105 Q89 111 96 105 M145 105 Q152 111 159 105" />`
    : `<ellipse class="cat-eye" cx="89" cy="105" rx="5" ry="9" />
       <ellipse class="cat-eye" cx="152" cy="105" rx="5" ry="9" />`;
  return `
    <svg class="cat-face ${compact ? "is-compact" : ""} ${clipping ? "is-clipping" : ""} ${low ? "is-low" : ""}"
      data-state="${escapeAttr(state)}"
      viewBox="0 0 240 180"
      role="img"
      aria-label="Rosto da gatinha NekoMind em estado ${escapeAttr(state)}">
      <title>Gatinha NekoMind com laço</title>
      <path class="cat-head" d="M40 78 Q33 59 42 27 Q45 17 59 21 L98 35 Q120 27 144 29 L180 20 Q196 17 199 31 Q204 54 200 76 Q211 89 211 110 Q210 151 164 162 Q120 175 76 161 Q29 148 29 109 Q29 89 40 78 Z" />
      <ellipse class="cat-cheek" cx="65" cy="128" rx="12" ry="6" />
      <ellipse class="cat-cheek" cx="175" cy="128" rx="12" ry="6" />
      ${eyes}
      <ellipse class="cat-nose-outline" cx="120" cy="126" rx="10" ry="7" />
      <ellipse class="cat-nose" cx="120" cy="126" rx="7" ry="5" />
      <path class="cat-whisker left" style="--voice:${level}" d="M75 118 L21 111 M75 129 L17 130 M79 139 L27 151" />
      <path class="cat-whisker right" style="--voice:${level}" d="M165 118 L219 111 M165 129 L223 130 M161 139 L213 151" />
      <ellipse class="cat-bow" cx="155" cy="45" rx="20" ry="29" transform="rotate(24 155 45)" />
      <ellipse class="cat-bow" cx="191" cy="59" rx="22" ry="20" transform="rotate(-28 191 59)" />
      <ellipse class="cat-bow-knot" cx="174" cy="55" rx="15" ry="13" />
      <circle class="voice-dot" cx="120" cy="174" r="${Math.max(3, Math.min(6, 3 + level / 25))}" />
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
  const result = snapshot.result;
  const evidence = result.evidence || {};
  const topics = result.topics.slice(0, 5).map((topic) => `<li>${escapeHtml(topic)}</li>`).join("");
  const duration = formatDuration(result.duration_seconds);
  const words = evidence.recognized_word_count ?? 0;
  const steps = evidence.completed_steps ?? 0;
  const hasSpeechEvidence = evidence.speech_detected === true;
  const facts = snapshot.is_demo
    ? ["Dados simulados e identificados", `${duration} de demonstração`, `${steps} etapas simuladas`]
    : hasSpeechEvidence ? [
      "Fala detectada",
      `${duration} de áudio`,
      `${words} ${words === 1 ? "palavra reconhecida" : "palavras reconhecidas"}`,
      `${steps} ${steps === 1 ? "etapa concluída" : "etapas concluídas"}`,
      evidence.local_processing ? "Processamento local" : "Origem identificada",
    ] : ["Validação de fala indisponível", "Resultado persistido", "Origem identificada"];
  return `<div class="public-evidence">
    <div class="evidence-heading">
      <span class="evidence-check" aria-hidden="true">✓</span>
      <div>
        <small>${escapeHtml(snapshot.is_demo ? "MODO DEMONSTRAÇÃO" : "SESSÃO PROCESSADA")}</small>
        <h2>O NekoMind confirmou</h2>
      </div>
    </div>
    <ul class="evidence-facts">${facts.map((fact) => `<li>${escapeHtml(fact)}</li>`).join("")}</ul>
    <div class="public-topics">
      <h3>Termos reconhecidos pelo NekoMind</h3>
      ${topics ? `<ul class="topic-strip">${topics}</ul>` : `<p class="empty-result">Nenhum termo destacado.</p>`}
    </div>
  </div>`;
}

function renderTouchResultCard(card, model) {
  if (card.kind === "topics") {
    return card.topics.length
      ? `<ul class="touch-topic-cloud">${card.topics.map((topic) => `<li>${escapeHtml(topic)}</li>`).join("")}</ul>`
      : `<p>${escapeHtml(card.value)}</p>`;
  }
  if (card.kind === "evidence") {
    const checks = model.is_demo
      ? "Dados simulados"
      : card.evidence?.speech_detected ? "Fala detectada · processo concluído" : "Processo concluído";
    return `<div class="touch-proof"><strong>${escapeHtml(card.value)}</strong><small>✓ ${escapeHtml(checks)}</small></div>`;
  }
  return `<p>${escapeHtml(card.value)}</p>`;
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
    <span><span class="card-nav-prefix">Resultado </span>${model.activeCard.cardIndex + 1} de ${model.activeCard.total}</span>
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
  if (snapshot.result && snapshot.experience_mode === "fair") {
    if (snapshot.is_demo) return "Demonstração concluída";
    return snapshot.result.evidence?.speech_detected ? "Funcionou!" : "Resultado concluído";
  }
  if (snapshot.result) return snapshot.result.subject || "Resultado NekoMind";
  if (snapshot.state === "recording") return "Explicação em andamento";
  if (snapshot.state === "processing") return "Análise em andamento";
  if (snapshot.state === "recovery") return "Aguardando operador";
  return "Toque no display para explicar";
}

function publicSubtitle(snapshot) {
  if (snapshot.result && snapshot.experience_mode === "fair") {
    if (snapshot.is_demo) return "Os dados desta sessão são simulados e estão identificados.";
    return snapshot.result.evidence?.speech_detected
      ? "O Mac captou a voz e concluiu o processamento da sessão."
      : "O resultado foi persistido, mas não há confirmação pública de fala.";
  }
  if (snapshot.result) return snapshot.result.summary;
  if (snapshot.state === "processing") return "A resposta muda quando a bancada confirma cada etapa.";
  if (snapshot.state === "recording") return "Áudio fica no Mac; esta tela não usa microfone.";
  return "A tela pública é somente leitura.";
}

function formatDuration(value) {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds < 0) return "0s";
  return `${Number(seconds.toFixed(1))}s`;
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
