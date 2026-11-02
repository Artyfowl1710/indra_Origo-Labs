(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];

  // One explicit UI state store: persistent preferences are versioned separately from
  // server-owned conversation data and volatile in-flight state. Actions are the only
  // supported mutation path; per-resource epochs prevent stale async responses winning.
  function createUIStateStore() {
    const allowedPanels = new Set(['chat','files','knowledge','approvals','runs','extensions','permissions','diagnostics']);
    const readLegacy = (key, fallback) => { try { const raw = localStorage.getItem(key); return raw == null ? fallback : raw; } catch { return fallback; } };
    const readJson = (key, fallback) => { try { const value = JSON.parse(readLegacy(key, 'null')); return value == null ? fallback : value; } catch { return fallback; } };
    const validConversation = (value) => typeof value === 'string' && /^[0-9a-f]{32}$/.test(value) ? value : null;
    const saved = readJson('indra.uiState.v2', {});
    const legacySkills = readJson('indra.selectedSkills', []);
    const selectedSkills = Array.isArray(saved.selectedSkills) ? saved.selectedSkills : legacySkills;
    let state = {
      schemaVersion: 2,
      activePanel: allowedPanels.has(saved.activePanel) ? saved.activePanel : 'chat',
      conversationId: validConversation(saved.conversationId) || validConversation(readLegacy('indra.activeConversation', null)),
      agentMode: saved.agentMode === 'plan' || readLegacy('indra.agentMode', 'build') === 'plan' ? 'plan' : 'build',
      selectedSkills: [...new Set((Array.isArray(selectedSkills) ? selectedSkills : []).filter(x => typeof x === 'string' && x.length <= 100))].slice(0, 6),
      focusMode: typeof saved.focusMode === 'boolean' ? saved.focusMode : readLegacy('indra.focusMode', 'off') === 'on',
      chatBusy: false,
      preparedContext: '',
      requestEpochs: Object.create(null),
      knowledge: { query: '', limit: 8, status: null, documents: [], results: null, loading: false }
    };
    const subscribers = new Set();
    function persist() {
      const durable = { schemaVersion: 2, activePanel: state.activePanel, conversationId: state.conversationId,
        agentMode: state.agentMode, selectedSkills: state.selectedSkills, focusMode: state.focusMode };
      try {
        localStorage.setItem('indra.uiState.v2', JSON.stringify(durable));
        // Read-only compatibility bridge for older builds; the v2 snapshot is canonical.
        if (state.conversationId) localStorage.setItem('indra.activeConversation', state.conversationId);
        else localStorage.removeItem('indra.activeConversation');
        localStorage.setItem('indra.agentMode', state.agentMode);
        localStorage.setItem('indra.selectedSkills', JSON.stringify(state.selectedSkills));
        localStorage.setItem('indra.focusMode', state.focusMode ? 'on' : 'off');
      } catch { /* Preferences remain valid for this page session when storage is blocked. */ }
    }
    function dispatch(action) {
      if (!action || typeof action.type !== 'string') return state;
      switch (action.type) {
        case 'PANEL_SET': if (allowedPanels.has(action.panel)) state.activePanel = action.panel; break;
        case 'CONVERSATION_SET': state.conversationId = validConversation(action.id); break;
        case 'CHAT_BUSY_SET': state.chatBusy = Boolean(action.value); break;
        case 'PREPARED_CONTEXT_SET': state.preparedContext = typeof action.value === 'string' ? action.value.slice(0, 12000) : ''; break;
        case 'AGENT_MODE_SET': if (action.mode === 'plan' || action.mode === 'build') state.agentMode = action.mode; break;
        case 'SKILLS_SET': state.selectedSkills = [...new Set((Array.isArray(action.skills) ? action.skills : []).filter(x => typeof x === 'string' && x.length <= 100))].slice(0, 6); break;
        case 'FOCUS_SET': state.focusMode = Boolean(action.value); break;
        case 'REQUEST_BEGIN': { const key = String(action.key || 'default'); state.requestEpochs[key] = (state.requestEpochs[key] || 0) + 1; action.token = state.requestEpochs[key]; break; }
        case 'KNOWLEDGE_PATCH': state.knowledge = { ...state.knowledge, ...(action.patch || {}) }; break;
        default: return state;
      }
      if (['PANEL_SET','CONVERSATION_SET','AGENT_MODE_SET','SKILLS_SET','FOCUS_SET'].includes(action.type)) persist();
      subscribers.forEach(fn => { try { fn(state, action); } catch { /* Observers cannot break state transitions. */ } });
      return state;
    }
    return { get: () => state, dispatch, subscribe: fn => { subscribers.add(fn); return () => subscribers.delete(fn); },
      beginRequest(key) { dispatch({ type: 'REQUEST_BEGIN', key }); return state.requestEpochs[String(key || 'default')]; },
      requestIsCurrent(key, token) { return state.requestEpochs[String(key || 'default')] === token; } };
  }
  const uiState = createUIStateStore();
  const remoteSignout = document.getElementById('remote-signout');
  if (remoteSignout && location.hostname.toLowerCase().endsWith('.ts.net')) {
    remoteSignout.hidden = false;
    remoteSignout.addEventListener('click', () => location.assign('/remote/logout'));
  }
  let history = [];
  let activeController = null;
  let toastTimer = null;
  let savedConversations = [];
  let sessionsReady = false;
  let initializationPromise = null;
  let stagedAttachments = [];
  let speechRecognition = null;
  let extensionData = null;
  let activePermissionRequest = null;
  let permissionDecisionBusy = false;
  let lastSandboxRunId = null;
  let lastSandboxProposablePaths = [];
  const savedAgentMode = uiState.get().agentMode;
  const idleWaiters = [];

  const agentModeSelect = document.querySelector('#agent-mode');
  if (agentModeSelect) { agentModeSelect.value = savedAgentMode; agentModeSelect.addEventListener('change', () => { uiState.dispatch({ type: 'AGENT_MODE_SET', mode: agentModeSelect.value }); toast(agentModeSelect.value === 'plan' ? 'Plan mode: read-only tool surface.' : 'Build mode: file changes are still approval-gated.'); }); }

  function esc(value) {
    return String(value ?? '').replace(/[&<>"']/g, (char) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[char]);
  }

  function toast(text) {
    const element = $('#toast');
    element.textContent = text;
    element.classList.add('show');
    if (toastTimer) window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => element.classList.remove('show'), 3200);
  }

  function setTheme(theme) {
    const next = theme === 'light' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    const toggle = $('#theme-toggle');
    if (toggle) {
      toggle.textContent = next === 'light' ? '☀ Light' : '☾ Dark';
      toggle.setAttribute('aria-label', `Switch to ${next === 'light' ? 'dark' : 'light'} mode`);
      toggle.setAttribute('aria-pressed', String(next === 'light'));
    }
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = next === 'light' ? '#f5f7ff' : '#090e1c';
    try { localStorage.setItem('indra.theme', next); } catch { /* Keep the current tab theme. */ }
  }
  setTheme(document.documentElement.dataset.theme);
  $('#theme-toggle')?.addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'));

  async function api(url, options = {}) {
    const headers = new Headers(options.headers || {});
    if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    const response = await fetch(url, { ...options, headers, credentials: 'same-origin' });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || data.error || `Request failed (HTTP ${response.status})`);
    return data;
  }

  function showPanel(name) {
    if (!['chat','files','knowledge','approvals','runs','extensions','permissions','diagnostics'].includes(name)) return;
    uiState.dispatch({ type: 'PANEL_SET', panel: name });
    $$('.panel').forEach((section) => {
      const active = section.id === `p-${name}`;
      section.classList.toggle('active', active);
      section.setAttribute('aria-hidden', String(!active));
    });
    $$('.nav').forEach((button) => {
      const active = button.dataset.panel === name;
      button.classList.toggle('active', active);
      if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
    });
    $('#title').textContent = ({
      chat: 'Copilot', files: 'Files & context', knowledge: 'Knowledge Studio', approvals: 'Approval queue',
      runs: 'Run history', extensions: 'Skills & plugins', permissions: 'Permissions', diagnostics: 'Diagnostics'
    })[name] || name;
    if (name === 'files') { loadFiles(); loadGitStatus(); }
    if (name === 'knowledge') loadRagStudio();
    if (name === 'approvals') loadActions();
    if (name === 'runs') { loadRuns(); loadMetrics(); loadFeedbackSummary(); }
    if (name === 'extensions') loadExtensions();
    if (name === 'permissions') loadPermissions();
    if (name === 'diagnostics') { loadDiagnostics(); refreshCapsules(); refreshProofLedger(); }
  }
  $$('.nav').forEach((button) => button.addEventListener('click', () => showPanel(button.dataset.panel)));
  $$('.panel').forEach((section) => section.setAttribute('aria-hidden', String(!section.classList.contains('active'))));
  $$('.nav').forEach((button) => {
    if (button.classList.contains('active')) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });

  function makeMessage(role, text, meta = '', shouldScroll = true) {
    const element = document.createElement('article');
    element.className = `msg ${role}`;
    const label = document.createElement('div');
    label.className = 'role';
    label.textContent = role === 'user' ? 'YOU' : 'INDRA ORIGO';
    const body = document.createElement('div');
    body.className = 'msg-body';
    body.textContent = text;
    element.append(label, body);
    if (meta) {
      const metadata = document.createElement('div');
      metadata.className = 'meta';
      metadata.textContent = meta;
      element.append(metadata);
    }
    $('#conversation').append(element);
    if (shouldScroll) element.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    return element;
  }

  function setMessage(element, text, meta = '') {
    element.querySelector('.msg-body').textContent = text;
    let metadata = element.querySelector('.meta');
    if (!metadata) {
      metadata = document.createElement('div');
      metadata.className = 'meta';
      element.append(metadata);
    }
    metadata.textContent = meta;
  }

  function setBusy(value) {
    uiState.dispatch({ type: 'CHAT_BUSY_SET', value });
    if (!value) while (idleWaiters.length) idleWaiters.shift()();
    $('#send').disabled = value;
    $('#send').innerHTML = value ? 'Running <span class="button-spinner" aria-hidden="true"></span>' : 'Send <span aria-hidden="true">↗</span>';
    $('#cancel').hidden = !value;
    $('#message').setAttribute('aria-busy', String(value));
  }

  async function streamChat(payload, bubble, signal) {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      body: JSON.stringify(payload), signal, credentials: 'same-origin'
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Request failed (HTTP ${response.status})`);
    }
    if (!response.body) throw new Error('This browser does not support streamed responses.');
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let run = null;
    let visibleText = '';
    let phase = 'Starting harness…';

    function processFrame(frame) {
      const dataLines = frame.split('\n').filter((line) => line.startsWith('data:'));
      if (!dataLines.length) return;
      const raw = dataLines.map((line) => line.slice(5).trimStart()).join('\n');
      let event;
      try { event = JSON.parse(raw); } catch { return; }
      if (event.type === 'token') {
        visibleText += event.text || '';
        bubble.querySelector('.msg-body').textContent = visibleText || phase;
      } else if (event.type === 'model_step_started') {
        phase = `Thinking · step ${event.step}`;
        if (!visibleText) bubble.querySelector('.msg-body').textContent = phase;
      } else if (event.type === 'tool_started') {
        phase = `Using ${event.tool || 'workspace tool'}…`;
        if (!visibleText) bubble.querySelector('.msg-body').textContent = phase;
      } else if (event.type === 'tool_finished') {
        phase = `Checked ${event.tool || 'workspace tool'} · ${event.category || 'finished'}`;
        if (!visibleText) bubble.querySelector('.msg-body').textContent = phase;
      } else if (event.type === 'warning') {
        phase = event.message || 'The run reached a limit.';
        bubble.querySelector('.msg-body').textContent = phase;
      } else if (event.type === 'permission_required') {
        showPermissionPrompt(event.permission || {});
      } else if (event.type === 'run_finished') {
        run = event.run;
      } else if (event.type === 'error') {
        throw new Error(event.message || 'The stream was interrupted.');
      }
    }

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        buffer = buffer.replace(/\r\n/g, '\n');
        const frames = buffer.split('\n\n');
        buffer = frames.pop() || '';
        for (const frame of frames) processFrame(frame);
      }
      buffer += decoder.decode();
      if (buffer.trim()) processFrame(buffer);
    } finally {
      try { reader.releaseLock(); } catch { /* stream already closed */ }
    }
    if (!run) throw new Error('The stream ended without a final run record. Check Diagnostics and local logs.');
    return run;
  }

  function trimmedHistory(userText, assistantText) {
    history.push({ role: 'user', content: userText.slice(0, 6000) },
      { role: 'assistant', content: assistantText.slice(0, 6000) });
    history = history.slice(-12);
    while (history.reduce((sum, item) => sum + item.content.length, 0) > 24000 && history.length > 2) history.shift();
  }

  function waitUntilIdle() {
    if (!uiState.get().chatBusy) return Promise.resolve();
    return new Promise((resolve) => idleWaiters.push(resolve));
  }

  function setCurrentConversation(id) {
    uiState.dispatch({ type: 'CONVERSATION_SET', id: id || null });
  }

  function historyFromMessages(messages) {
    history = (messages || []).slice(-12).map((item) => ({
      role: item.role,
      content: String(item.content || '').slice(0, 6000),
    })).filter((item) => ['user', 'assistant'].includes(item.role));
    while (history.reduce((sum, item) => sum + item.content.length, 0) > 24000 && history.length > 1) history.shift();
  }

  const RUN_FEEDBACK = [
    { value: 'useful', label: 'Useful', aria: 'Mark this run useful' },
    { value: 'incorrect', label: 'Incorrect', aria: 'Mark this run incorrect' },
    { value: 'incomplete', label: 'Incomplete', aria: 'Mark this run incomplete' },
    { value: 'risky', label: 'Risky / unsafe', aria: 'Mark this run risky or unsafe' },
  ];

  function renderAnswerTrustNote(bubble) {
    if (!bubble || bubble.querySelector('.trust-note')) return;
    const note = document.createElement('p');
    note.className = 'trust-note';
    note.setAttribute('role', 'note');
    note.textContent = 'AI-generated response. Traces and linked evidence can help inspection, but do not guarantee correctness.';
    bubble.append(note);
  }

  function renderRunFeedback(bubble, runId, conversationId, selected = null) {
    if (!bubble || !/^[0-9a-f]{32}$/.test(String(runId || '')) || !/^[0-9a-f]{32}$/.test(String(conversationId || ''))) return;
    bubble.querySelector('.run-feedback')?.remove();
    const wrapper = document.createElement('section');
    wrapper.className = 'run-feedback';
    wrapper.dataset.runId = runId;
    wrapper.dataset.conversationId = conversationId;
    wrapper.dataset.rating = selected || '';
    wrapper.setAttribute('aria-label', 'Optional feedback on this answer');

    const disclosure = document.createElement('p');
    disclosure.className = 'feedback-disclosure';
    disclosure.textContent = 'Optional: rate this result. Your rating is saved locally only; it is not sent to the model or used for training.';
    const group = document.createElement('div');
    group.className = 'feedback-rating';
    group.setAttribute('role', 'group');
    group.setAttribute('aria-label', 'Rate this answer');
    const status = document.createElement('p');
    status.className = 'feedback-status';
    status.setAttribute('aria-live', 'polite');
    status.textContent = selected ? `Your rating: ${RUN_FEEDBACK.find((item) => item.value === selected)?.label || selected}. You can change or remove it.` : 'No rating saved.';
    for (const option of RUN_FEEDBACK) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'feedback-choice';
      button.dataset.rating = option.value;
      button.textContent = option.label;
      button.setAttribute('aria-label', option.aria);
      button.setAttribute('aria-pressed', String(selected === option.value));
      button.addEventListener('click', () => saveRunFeedback(wrapper, option.value));
      group.append(button);
    }
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'feedback-remove';
    remove.textContent = 'Remove rating';
    remove.hidden = !selected;
    remove.addEventListener('click', () => removeRunFeedback(wrapper));
    wrapper.append(disclosure, group, status, remove);
    bubble.append(wrapper);
  }

  async function saveRunFeedback(wrapper, rating) {
    const buttons = [...wrapper.querySelectorAll('button')];
    buttons.forEach((button) => { button.disabled = true; });
    const status = wrapper.querySelector('.feedback-status');
    status.textContent = 'Saving rating locally…';
    try {
      await api('/api/feedback', { method: 'POST', body: JSON.stringify({
        run_id: wrapper.dataset.runId,
        conversation_id: wrapper.dataset.conversationId,
        rating,
      }) });
      wrapper.dataset.rating = rating;
      wrapper.querySelectorAll('[data-rating]').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.rating === rating)));
      wrapper.querySelector('.feedback-remove').hidden = false;
      status.textContent = `Saved locally: ${RUN_FEEDBACK.find((item) => item.value === rating)?.label || rating}. Change or remove this rating any time.`;
      loadFeedbackSummary();
    } catch (error) {
      status.textContent = `Rating not saved: ${error.message}`;
    } finally { buttons.forEach((button) => { button.disabled = false; }); }
  }

  async function removeRunFeedback(wrapper) {
    const buttons = [...wrapper.querySelectorAll('button')];
    buttons.forEach((button) => { button.disabled = true; });
    const status = wrapper.querySelector('.feedback-status');
    status.textContent = 'Removing rating…';
    try {
      await api(`/api/feedback/${encodeURIComponent(wrapper.dataset.runId)}?conversation_id=${encodeURIComponent(wrapper.dataset.conversationId)}`, { method: 'DELETE' });
      wrapper.dataset.rating = '';
      wrapper.querySelectorAll('[data-rating]').forEach((button) => button.setAttribute('aria-pressed', 'false'));
      wrapper.querySelector('.feedback-remove').hidden = true;
      status.textContent = 'Rating removed. No rating is required.';
      loadFeedbackSummary();
    } catch (error) {
      status.textContent = `Rating could not be removed: ${error.message}`;
    } finally { buttons.forEach((button) => { button.disabled = false; }); }
  }

  async function refreshVisibleFeedback() {
    try {
      const data = await api(`/api/feedback?conversation_id=${encodeURIComponent(uiState.get().conversationId || '')}`);
      $$('.run-feedback').forEach((wrapper) => {
        const selected = data.by_run?.[wrapper.dataset.runId] || null;
        wrapper.dataset.rating = selected || '';
        wrapper.querySelectorAll('[data-rating]').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.rating === selected)));
        wrapper.querySelector('.feedback-remove').hidden = !selected;
        wrapper.querySelector('.feedback-status').textContent = selected
          ? `Your rating: ${RUN_FEEDBACK.find((item) => item.value === selected)?.label || selected}. You can change or remove it.`
          : 'No rating saved.';
      });
    } catch { /* Feedback is optional; a read failure must not block chat. */ }
  }

  function showConversation(row) {
    setCurrentConversation(row.conversation_id);
    historyFromMessages(row.messages || []);
    const container = $('#conversation');
    container.replaceChildren();
    const messages = row.messages || [];
    messages.forEach((item, index) => {
      const meta = item.status ? `${item.status}${item.run_id ? ` · run ${item.run_id}` : ''}` : '';
      const bubble = makeMessage(item.role, item.content, meta, index === messages.length - 1);
      if (item.role === 'assistant' && item.run_id) {
        renderAnswerTrustNote(bubble);
        renderRunFeedback(bubble, item.run_id, row.conversation_id);
      }
    });
    refreshVisibleFeedback();
    $('#suggestions').hidden = (row.messages || []).length > 0;
    $('#message').value = '';
    showPanel('chat');
    refreshSessions().catch(() => {});
  }

  async function refreshSessions() {
    const rows = await api('/api/sessions');
    savedConversations = rows;
    const container = $('#sessions');
    if (!rows.length) {
      container.innerHTML = '<div class="session-empty">Your saved conversations appear here.</div>';
      return;
    }
    container.innerHTML = rows.map((row) => {
      const active = row.conversation_id === uiState.get().conversationId;
      const workspaceName = String(row.workspace || '').split(/[\\/]/).filter(Boolean).pop() || 'workspace';
      return `<div class="session-row ${active ? 'active' : ''}"><button class="session-open" data-session="${esc(row.conversation_id)}" type="button" aria-current="${active ? 'page' : 'false'}"><span>${esc(row.title || 'New conversation')}</span><small>${Number(row.message_count || 0)} messages · ${esc(workspaceName)}</small></button><button class="session-delete" data-delete-session="${esc(row.conversation_id)}" type="button" title="Delete saved conversation" aria-label="Delete ${esc(row.title || 'conversation')}">×</button></div>`;
    }).join('');
    $$('[data-session]').forEach((button) => button.addEventListener('click', () => openConversation(button.dataset.session)));
    $$('[data-delete-session]').forEach((button) => button.addEventListener('click', () => deleteConversation(button.dataset.deleteSession)));
  }

  async function openConversation(id, options = {}) {
    if (uiState.get().chatBusy) {
      toast('Finish or cancel the active run before switching conversations.');
      return;
    }
    try {
      const row = await api(`/api/sessions/${encodeURIComponent(id)}`);
      const settings = await api('/api/settings');
      const norm = (path) => String(path || '').replaceAll('\\', '/').replace(/\/+$/, '').toLowerCase();
      if (norm(settings.workspace) !== norm(row.workspace)) {
        const switchWorkspace = options.initial
          ? window.confirm(`This saved conversation belongs to a different workspace. Switch to:

${row.workspace}`)
          : window.confirm(`Switch the active workspace to continue this conversation?

${row.workspace}`);
        if (!switchWorkspace) {
          if (options.initial) {
            setCurrentConversation(null);
            history = [];
            $('#conversation').replaceChildren();
            $('#suggestions').hidden = false;
          }
          return;
        }
        await api('/api/workspace/select', { method: 'POST', body: JSON.stringify({ path: row.workspace }) });
        await refreshStatus();
        await loadFiles();
      }
      showConversation(row);
      sessionsReady = true;
    } catch (error) {
      if (options.initial) {
        setCurrentConversation(null);
        await createConversation({ render: true });
      } else toast(error.message);
    }
  }

  async function createConversation(options = {}) {
    if (uiState.get().chatBusy) {
      if (!window.confirm('Cancel the active run and start a new conversation?')) return;
      activeController?.abort();
      await waitUntilIdle();
    }
    try {
      const row = await api('/api/sessions', { method: 'POST', body: JSON.stringify({ title: 'New conversation' }) });
      setCurrentConversation(row.conversation_id);
      history = [];
      $('#conversation').replaceChildren();
      $('#suggestions').hidden = false;
      $('#message').value = '';
      if (options.render !== false) showPanel('chat');
      await refreshSessions();
      return row;
    } catch (error) {
      toast(`Could not create a saved conversation: ${error.message}`);
      throw error;
    }
  }

  async function deleteConversation(id) {
    const row = savedConversations.find((item) => item.conversation_id === id);
    if (!window.confirm(`Delete the saved conversation “${row?.title || 'conversation'}”? This cannot be undone.`)) return;
    try {
      await api(`/api/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' });
      if (id === uiState.get().conversationId) {
        setCurrentConversation(null);
        history = [];
        $('#conversation').replaceChildren();
        $('#suggestions').hidden = false;
        await createConversation({ render: false });
      }
      await refreshSessions();
      toast('Saved conversation deleted.');
    } catch (error) { toast(error.message); }
  }

  function initializeConversations() {
    if (initializationPromise) return initializationPromise;
    initializationPromise = (async () => {
      try {
        const rows = await api('/api/sessions');
        savedConversations = rows;
        const savedId = uiState.get().conversationId && rows.some((row) => row.conversation_id === uiState.get().conversationId)
          ? uiState.get().conversationId : (rows[0]?.conversation_id || null);
        if (savedId) await openConversation(savedId, { initial: true });
        if (!uiState.get().conversationId) await createConversation({ render: true });
        await refreshSessions();
        sessionsReady = true;
      } catch (error) {
        $('#sessions').innerHTML = `<div class="session-empty">Saved chats unavailable: ${esc(error.message)}</div>`;
        sessionsReady = false;
      }
    })();
    return initializationPromise;
  }

  const TEXT_EXTENSIONS = new Set(['txt','md','markdown','csv','json','jsonl','py','js','ts','tsx','jsx','html','css','xml','yaml','yml','toml','ini','log','sql','sh','bat','ps1']);
  const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
  const MAX_UPLOADS = 4;
  function fileExtension(name) { return String(name).split('.').pop().toLowerCase(); }
  function fileMime(file) {
    const typed = String(file.type || '').toLowerCase().split(';')[0];
    if (typed && typed !== 'application/octet-stream') return typed;
    return ({ png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp', pdf: 'application/pdf',
      txt: 'text/plain', md: 'text/markdown', markdown: 'text/markdown', csv: 'text/csv', json: 'application/json', jsonl: 'application/json',
      py: 'text/x-python', js: 'text/javascript', ts: 'text/javascript', tsx: 'text/javascript', jsx: 'text/javascript',
      html: 'text/html', css: 'text/css', xml: 'application/xml', yaml: 'text/yaml', yml: 'text/yaml', toml: 'text/plain',
      ini: 'text/plain', log: 'text/x-log', sql: 'text/plain', sh: 'text/plain', bat: 'text/plain', ps1: 'text/plain' })[fileExtension(file.name)] || typed || 'application/octet-stream';
  }
  function classifyFile(file) {
    const ext = fileExtension(file.name), mime = fileMime(file);
    if (mime === 'application/pdf' || ext === 'pdf') return 'pdf';
    if (TEXT_EXTENSIONS.has(ext) || mime.startsWith('text/') || ['application/json','application/xml','application/javascript','application/yaml'].includes(mime)) return 'text';
    if (['image/png','image/jpeg','image/webp'].includes(mime)) return 'image';
    if (mime.startsWith('image/')) return 'preview-image';
    if (mime.startsWith('audio/')) return 'preview-audio';
    if (mime.startsWith('video/')) return 'preview-video';
    return 'preview-only';
  }
  function formatBytes(bytes) { return bytes < 1024 ? `${bytes} B` : bytes < 1024*1024 ? `${(bytes/1024).toFixed(1)} KB` : `${(bytes/1024/1024).toFixed(2)} MB`; }
  function fileAsBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error(`Couldn't read ${file.name}.`));
      reader.onload = () => {
        const value = String(reader.result || '');
        const comma = value.indexOf(',');
        if (comma < 0) reject(new Error(`Couldn't encode ${file.name}.`));
        else resolve(value.slice(comma + 1));
      };
      reader.readAsDataURL(file);
    });
  }
  function revokeAttachment(row) { if (row.previewUrl) URL.revokeObjectURL(row.previewUrl); }
  function clearAttachments() {
    stagedAttachments.forEach(revokeAttachment);
    stagedAttachments = [];
    renderAttachments();
    $('#file-input').value = '';
  }
  function renderAttachments() {
    const host = $('#upload-previews');
    host.replaceChildren();
    host.hidden = !stagedAttachments.length;
    stagedAttachments.forEach((row, index) => {
      const card = document.createElement('div'); card.className = 'upload-card';
      const head = document.createElement('div'); head.className = 'upload-head';
      const name = document.createElement('div'); name.className = 'upload-name'; name.textContent = row.file.name;
      const remove = document.createElement('button'); remove.className = 'upload-remove'; remove.type = 'button'; remove.textContent = '×';
      remove.setAttribute('aria-label', `Remove ${row.file.name}`);
      remove.addEventListener('click', () => { revokeAttachment(stagedAttachments[index]); stagedAttachments.splice(index, 1); renderAttachments(); });
      head.append(name, remove); card.append(head);
      const meta = document.createElement('div'); meta.className = 'upload-meta';
      meta.textContent = `${row.kind.replace('preview-', '')} · ${formatBytes(row.file.size)} · ${row.kind === 'text' || row.kind === 'pdf' ? 'text will be sent' : row.kind === 'image' ? ($('#send-images').checked ? 'image will be sent' : 'preview only; enable image sending') : 'preview only; not sent to model'}`;
      card.append(meta);
      if (row.kind === 'image' || row.kind === 'preview-image') {
        const img = document.createElement('img'); img.className = 'upload-image'; img.src = row.previewUrl; img.alt = `Preview of ${row.file.name}`; card.append(img);
      } else if (row.kind === 'pdf') {
        const frame = document.createElement('iframe'); frame.className = 'upload-pdf'; frame.src = row.previewUrl; frame.title = `Local preview of ${row.file.name}`; frame.setAttribute('sandbox',''); card.append(frame);
      } else if (row.kind === 'preview-audio' || row.kind === 'preview-video') {
        const media = document.createElement(row.kind === 'preview-audio' ? 'audio' : 'video'); media.className = 'upload-media'; media.src = row.previewUrl; media.controls = true; media.preload = 'metadata';
        if (row.kind === 'preview-video') media.playsInline = true;
        card.append(media);
      } else if (row.kind === 'text') {
        const preview = document.createElement('pre'); preview.className = 'upload-text'; preview.textContent = row.textContent || 'Reading text preview…'; card.append(preview);
      } else {
        const warning = document.createElement('div'); warning.className = 'upload-warning'; warning.textContent = 'Preview only. This file type is not forwarded to the model.'; card.append(warning);
      }
      host.append(card);
    });
  }
  $('#attach-files').addEventListener('click', () => $('#file-input').click());
  $('#file-input').addEventListener('change', async (event) => {
    const files = [...(event.target.files || [])];
    if (stagedAttachments.length + files.length > MAX_UPLOADS) { toast(`Attach at most ${MAX_UPLOADS} files per message.`); event.target.value = ''; return; }
    for (const file of files) {
      if (file.size <= 0 || file.size > MAX_UPLOAD_BYTES) { toast(`${file.name}: files must be between 1 byte and 5 MiB.`); continue; }
      const kind = classifyFile(file);
      const row = { file, kind, textContent: '', previewUrl: URL.createObjectURL(file) };
      if (kind === 'text') {
        try { row.textContent = (await file.text()).slice(0, 24000); }
        catch { row.textContent = '[Browser could not read this file as text.]'; }
      }
      stagedAttachments.push(row);
    }
    renderAttachments();
    event.target.value = '';
    if (files.length) toast('File previews are local. Text content is sent with your next message; PDF parsing is disabled by default for security. Images require the explicit send-images toggle.');
  });
  $('#send-images').addEventListener('change', () => renderAttachments());

  function setVoiceStatus(message, active = false) {
    const node = $('#voice-status'); node.textContent = message; node.classList.toggle('active', active);
  }
  $('#voice-input').addEventListener('click', () => {
    if (speechRecognition) { speechRecognition.stop(); speechRecognition = null; setVoiceStatus('Voice input stopped.'); $('#voice-input').textContent = '◉ Voice input'; return; }
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) { setVoiceStatus('Voice recognition is not supported in this browser. Try Chrome/Edge or type instead.'); toast('This browser does not expose SpeechRecognition.'); return; }
    try {
      const recognizer = new Recognition(); speechRecognition = recognizer;
      recognizer.lang = navigator.language || 'en-IN'; recognizer.continuous = false; recognizer.interimResults = true;
      const priorText = $('#message').value.trim();
      recognizer.onstart = () => { setVoiceStatus('Listening… speak now.', true); $('#voice-input').textContent = '■ Stop listening'; };
      recognizer.onresult = (event) => {
        let finalText = '', interim = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0]?.transcript || '';
          if (event.results[i].isFinal) finalText += transcript; else interim += transcript;
        }
        const addition = (finalText || interim).trim();
        if (addition) $('#message').value = [priorText, addition].filter(Boolean).join(priorText ? ' ' : '').slice(0, 12000);
      };
      recognizer.onerror = (event) => setVoiceStatus(`Voice recognition error: ${event.error || 'unknown error'}.`);
      recognizer.onend = () => { speechRecognition = null; $('#voice-input').textContent = '◉ Voice input'; setVoiceStatus('Dictation ended. Review the transcript before sending.'); $('#message').focus(); };
      recognizer.start();
    } catch (error) { speechRecognition = null; setVoiceStatus(`Couldn't start voice input: ${error.message}`); }
  });
  $('#stop-speech').addEventListener('click', () => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    if (speechRecognition) { speechRecognition.stop(); speechRecognition = null; }
    $('#voice-input').textContent = '◉ Voice input'; setVoiceStatus('Voice playback/listening stopped.');
  });
  function speakResponse(text) {
    if (!$('#voice-output').checked) return;
    if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') { setVoiceStatus('Voice output is not supported in this browser.'); return; }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(String(text || '').slice(0, 10000));
    utterance.lang = navigator.language || 'en-IN';
    utterance.onstart = () => setVoiceStatus('Speaking response…', true);
    utterance.onend = () => setVoiceStatus('Finished speaking.');
    utterance.onerror = () => setVoiceStatus('Browser voice output stopped or failed.');
    window.speechSynthesis.speak(utterance);
  }
  async function attachmentsForRequest() {
    const result = [];
    for (const row of stagedAttachments) {
      if (row.kind === 'text') result.push({ name: row.file.name, mime_type: fileMime(row.file), kind: 'text', text_content: row.textContent });
      else if (row.kind === 'pdf') result.push({ name: row.file.name, mime_type: 'application/pdf', kind: 'pdf', data_base64: await fileAsBase64(row.file) });
      else if (row.kind === 'image' && $('#send-images').checked) result.push({ name: row.file.name, mime_type: fileMime(row.file), kind: 'image', data_base64: await fileAsBase64(row.file) });
    }
    return result;
  }

  async function submitMessage(event) {
    event?.preventDefault();
    if (uiState.get().chatBusy) return;
    let text = $('#message').value.trim();
    let requestAttachments;
    try { requestAttachments = await attachmentsForRequest(); }
    catch (error) { toast(error.message); return; }
    if (!text && !requestAttachments.length) { toast('Write a message or attach a supported text file; PDF parsing is disabled by default. Enable image sending for an attached image.'); return; }
    if (!text) text = 'Please inspect the attached file(s) and summarize the important contents.';
    const userDisplay = text + (requestAttachments.length ? `\n\nAttached: ${requestAttachments.map((item) => item.name).join(', ')}` : '');
    if (!uiState.get().conversationId) {
      await initializeConversations();
      if (!uiState.get().conversationId) { toast('Saved chat storage is unavailable. Check the local server.'); return; }
    }
    $('#suggestions').hidden = true;
    makeMessage('user', userDisplay);
    $('#message').value = '';
    const bubble = makeMessage('assistant', 'Starting harness…');
    const controller = new AbortController();
    activeController = controller;
    setBusy(true);
    let contextForTurn = uiState.get().preparedContext;
    try {
      uiState.dispatch({ type: 'PREPARED_CONTEXT_SET', value: '' });
      $('#usecontext').disabled = true;
      $('#usecontext').textContent = 'Use in next chat';
      $('#context-attachment-indicator').hidden = true;
      const mode = $('#agent-mode')?.value === 'plan' ? 'plan' : 'build';
      const run = await streamChat({ message: text, attachments: requestAttachments, mode, history, conversation_id: uiState.get().conversationId, ...(contextForTurn ? { context: contextForTurn } : {}), ...(uiState.get().selectedSkills.length ? { skills: uiState.get().selectedSkills } : {}) }, bubble, controller.signal);
      setMessage(bubble, run.answer || 'The run returned no answer.',
        `${run.mode === 'plan' ? 'Plan' : 'Build'} mode · ${run.profile || 'balanced'} profile · ${run.tool_calls ?? 0} tool calls · ${Math.round(run.duration_ms || 0)} ms · ${run.status || 'finished'}${run.context_attached ? ` · workspace context ${Number(run.context_chars || 0).toLocaleString()} chars` : ''}${uiState.get().selectedSkills.length ? ` · skills ${uiState.get().selectedSkills.join(', ')}` : ''}`);
      if (run.run_id && uiState.get().conversationId) {
        renderAnswerTrustNote(bubble);
        renderRunFeedback(bubble, run.run_id, uiState.get().conversationId);
        refreshVisibleFeedback();
      }
      trimmedHistory(text, run.answer || '');
      speakResponse(run.answer || '');
      clearAttachments();
      refreshSessions().catch(() => {});
      if (run.trace?.length) {
        const trace = run.trace.map((item, index) => `${index + 1}. ${item.tool} · ${item.category} · ${item.duration_ms} ms\n${JSON.stringify(item.result).slice(0, 500)}`).join('\n\n');
        makeMessage('assistant', trace, `RUN TRACE · ${run.run_id}`);
      }
      loadActions();
      loadMetrics();
    } catch (error) {
      if (contextForTurn) {
        uiState.dispatch({ type: 'PREPARED_CONTEXT_SET', value: contextForTurn });
        $('#usecontext').disabled = false;
        $('#usecontext').textContent = 'Attached · retry next chat';
        $('#context-attachment-indicator').hidden = false;
        $('#context-attachment-label').textContent = `Workspace context attached · ${contextForTurn.length.toLocaleString()} characters (next turn only)`;
      }
      if (controller.signal.aborted || error.name === 'AbortError') {
        setMessage(bubble, 'Run cancelled. The harness will record cancellation when the server receives the disconnect.', 'CANCELLED');
      } else {
        setMessage(bubble, `I couldn't complete that request.\n\n${error.message}\n\nOpen Diagnostics or inspect logs/server-error.log.`, 'REQUEST FAILED');
      }
    } finally {
      activeController = null;
      setBusy(false);
      $('#message').focus();
    }
  }
  $('#form').addEventListener('submit', submitMessage);
  document.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      openCommandPalette();
    }
  });
  $('#cancel').addEventListener('click', () => activeController?.abort());
  $('#message').addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') submitMessage(event);
    if (event.key === 'Escape' && uiState.get().chatBusy) activeController?.abort();
  });
  $$('.suggestions [data-prompt]').forEach((button) => button.addEventListener('click', () => {
    $('#message').value = button.dataset.prompt;
    $('#message').focus();
  }));
  $('#new').addEventListener('click', () => createConversation({ render: true }).catch(() => {}));
  $('#refresh-sessions').addEventListener('click', () => refreshSessions().then(() => toast('Recent conversations refreshed.')).catch((error) => toast(error.message)));

  let scratchpadDirty = false;
  async function loadScratchpad() {
    const content = $('#scratchpad-content');
    if (!content || scratchpadDirty) return;
    try {
      const data = await api('/api/scratchpad');
      content.value = data.content || '';
      $('#scratchpad-status').textContent = `${content.value.length.toLocaleString()} / ${Number(data.max_chars).toLocaleString()} characters · saved locally`;
    } catch (error) { $('#scratchpad-status').textContent = `Scratchpad unavailable: ${error.message}`; }
  }
  $('#scratchpad-save')?.addEventListener('click', async () => {
    const button = $('#scratchpad-save'); button.disabled = true; button.textContent = 'Saving…';
    try {
      const value = $('#scratchpad-content').value;
      const result = await api('/api/scratchpad', { method: 'PUT', body: JSON.stringify({ content: value }) });
      scratchpadDirty = false;
      $('#scratchpad-status').textContent = `${Number(result.chars).toLocaleString()} / ${Number(result.max_chars).toLocaleString()} characters · saved locally`;
      toast('Scratchpad saved on this workstation.');
    } catch (error) { $('#scratchpad-status').textContent = `Save failed: ${error.message}`; toast(error.message); }
    finally { button.disabled = false; button.textContent = 'Save notes'; }
  });
  $('#scratchpad-content')?.addEventListener('input', () => {
    const node = $('#scratchpad-content'); scratchpadDirty = true; $('#scratchpad-status').textContent = `${node.value.length.toLocaleString()} / 30,000 characters · unsaved edits`;
  });

  async function loadProviderProfiles() {
    try {
      const data = await api('/api/providers');
      $('#provider-profile').value = data.active || 'local';
      const privacy = $('#inference-privacy');
      if (privacy) {
        const hosted = data.active === 'hosted';
        privacy.classList.toggle('hosted', hosted);
        privacy.textContent = hosted
          ? '◈ Hosted inference · prompts, attachments, and selected context leave this PC'
          : '◇ Local profile · inspect the configured gateway in Diagnostics';
      }
      const descriptions = (data.profiles || []).map((profile) => `${profile.label}: ${profile.configured ? `configured (${profile.endpoint})` : 'not configured'}`);
      $('#provider-profile-help').textContent = `${descriptions.join(' · ')}. API keys are never returned to this page.`;
    } catch (error) { $('#provider-profile-help').textContent = `Provider profiles unavailable: ${error.message}`; }
  }
  $('#save-provider-profile')?.addEventListener('click', async () => {
    const button = $('#save-provider-profile'); button.disabled = true; button.textContent = 'Switching…';
    try {
      const result = await api('/api/provider/profile', { method: 'POST', body: JSON.stringify({ profile: $('#provider-profile').value }) });
      toast(`Provider profile changed to ${result.active}. No inference was run.`);
      await Promise.all([loadProviderProfiles(), refreshModelOptions(), refreshStatus(), loadCapabilities()]);
    } catch (error) { toast(error.message); await loadProviderProfiles(); }
    finally { button.disabled = false; button.textContent = 'Switch profile'; }
  });

  async function refreshStatus() {
    try {
      const settings = await api('/api/settings');
      loadProviderProfiles().catch(() => {});
      loadScratchpad().catch(() => {});
      $('#workspace-path').value = settings.workspace;
      $('#root').textContent = `Workspace root: ${settings.workspace}`;
      $('#model').textContent = 'Checking model…';
      $('#modelsub').textContent = `${settings.model_endpoint || 'configured gateway'} · probing`;
      $('#dot').classList.remove('ok');
      // Model discovery is deliberately backgrounded: a sleeping/offline model must not delay UI startup.
      api('/api/models').then((modelData) => {
        const endpointHost = (() => { try { return new URL(settings.model_endpoint).host; } catch { return 'configured gateway'; } })();
        if (modelData.models?.length) {
          $('#model').textContent = modelData.resolved || modelData.models[0];
          $('#modelsub').textContent = `${endpointHost} · connected`;
          $('#dot').classList.add('ok');
          $('#footstatus').textContent = 'Model connected · writes require approval';
        } else {
          $('#model').textContent = 'No model connected';
          $('#modelsub').textContent = 'Start llama-swap or open Diagnostics';
          $('#dot').classList.remove('ok');
          $('#footstatus').textContent = 'UI online · model gateway unavailable';
        }
      }).catch(() => {
        $('#model').textContent = 'No model connected';
        $('#modelsub').textContent = 'Start llama-swap or open Diagnostics';
        $('#dot').classList.remove('ok');
        $('#footstatus').textContent = 'UI online · model gateway unavailable';
      });
    } catch {
      $('#model').textContent = 'API unavailable';
      $('#modelsub').textContent = 'Check local server logs';
      $('#dot').classList.remove('ok');
      $('#footstatus').textContent = 'Status check failed';
    }
  }

  async function loadGitStatus() {
    const summary = $('#git-summary'); const output = $('#git-status-output');
    if (!summary || !output) return;
    summary.textContent = 'Inspecting read-only Git status…';
    try {
      const data = await api('/api/git/status');
      if (!data.is_repository) {
        summary.textContent = data.error || 'This workspace is not a Git repository.';
        output.textContent = 'Initialize or open an existing repository to see branch and change status.';
        return;
      }
      if (data.error) {
        summary.textContent = data.error; output.textContent = 'Git status could not be read.'; return;
      }
      summary.textContent = `${data.branch || 'unknown branch'} · ${Number(data.entries?.length || 0)} entries · ${Number(data.modified || 0)} modified · ${Number(data.added || 0)} added · ${Number(data.deleted || 0)} deleted`;
      output.textContent = `${(data.entries || []).join('\n') || '(No tracked or untracked changes detected)'}${data.truncated ? '\n… output truncated' : ''}\n\n${data.scope || 'Read-only status.'}`;
    } catch (error) { summary.textContent = `Git status unavailable: ${error.message}`; output.textContent = 'Git inspection failed safely.'; }
  }
  $('#git-refresh').addEventListener('click', loadGitStatus);

  async function loadFiles() {
    try {
      const data = await api('/api/workspace');
      $('#root').textContent = `Workspace root: ${data.root} · showing at most ${data.files.length} files`;
      $('#workspace-path').value = data.root;
      const container = $('#files');
      if (!data.files.length) {
        container.innerHTML = '<div class="empty">No safe text files found yet. Select the project folder above or add a sample file.</div>';
        return;
      }
      container.innerHTML = data.files.map((file) => `<button class="file" type="button" data-path="${esc(file.path)}"><span class="file-icon">▤</span><span class="file-name">${esc(file.path)}</span><span class="filesize">${Number(file.size).toLocaleString()} B</span></button>`).join('');
      $$('.file[data-path]').forEach((button) => button.addEventListener('click', () => readFile(button.dataset.path)));
    } catch (error) {
      $('#files').innerHTML = `<div class="empty">${esc(error.message)}</div>`;
    }
  }

  async function readFile(path) {
    try {
      const data = await api(`/api/workspace/read?path=${encodeURIComponent(path)}`);
      $('#previewtitle').textContent = data.path || path;
      $('#preview').textContent = data.content;
    } catch (error) { toast(error.message); }
  }
  $('#reload').addEventListener('click', loadFiles);

  async function searchWorkspace() {
    const query = $('#filesearch').value.trim();
    const results = $('#searchresults');
    if (!query) { toast('Type a word or phrase to search the current workspace.'); $('#filesearch').focus(); return; }
    const button = $('#searchfiles');
    button.disabled = true; button.textContent = 'Searching…'; results.hidden = false;
    results.innerHTML = '<div class="empty">Searching readable project text…</div>';
    try {
      const data = await api(`/api/workspace/search?q=${encodeURIComponent(query)}`);
      const rows = data.matches || [];
      const note = `<div class="search-summary">${Number(rows.length).toLocaleString()} match(es) · ${Number(data.scanned_files || 0).toLocaleString()} files scanned${data.truncated ? ' · results bounded' : ''}</div>`;
      const content = rows.map((row) => `<button type="button" class="search-hit" data-search-path="${esc(row.path)}"><span class="search-hit-head"><b>${esc(row.path)}</b><small>line ${Number(row.line || 0)}</small></span><code>${esc(row.text || '')}</code></button>`).join('');
      results.innerHTML = note + (content || '<div class="empty">No matches found in readable, non-sensitive text files.</div>');
      $$('[data-search-path]').forEach((item) => item.addEventListener('click', () => readFile(item.dataset.searchPath)));
      toast(rows.length ? `Found ${rows.length} match(es).` : 'No matches found.');
    } catch (error) { results.innerHTML = `<div class="empty">${esc(error.message)}</div>`; }
    finally { button.disabled = false; button.textContent = 'Search'; }
  }
  $('#searchfiles').addEventListener('click', searchWorkspace);
  $('#filesearch').addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); searchWorkspace(); } });

  $('#choose-workspace').addEventListener('click', async () => {
    const path = $('#workspace-path').value.trim();
    if (!path) { toast('Enter the local folder path first.'); return; }
    if (!window.confirm(`Allow Indra to inspect files under this folder?\n\n${path}\n\nThe app will not grant access outside the selected root.`)) return;
    const button = $('#choose-workspace');
    button.disabled = true;
    try {
      const result = await api('/api/workspace/select', { method: 'POST', body: JSON.stringify({ path }) });
      history = [];
      $('#conversation').replaceChildren();
      $('#suggestions').hidden = false;
      setCurrentConversation(null);
      await createConversation({ render: false });
      $('#root').textContent = `Workspace root: ${result.workspace} · ${result.files} files`;
      $('#previewtitle').textContent = 'FILE PREVIEW';
      $('#preview').textContent = 'Choose a text file to inspect it.';
      $('#contextpreview').textContent = 'Build a context pack to preview this workspace.';
      $('#contextmeta').textContent = 'Not built yet';
      uiState.dispatch({ type: 'PREPARED_CONTEXT_SET', value: '' });
      $('#usecontext').disabled = true;
      $('#usecontext').textContent = 'Use in next chat';
      $('#context-attachment-indicator').hidden = true;
      toast('Workspace changed. Conversation context was cleared.');
      await loadFiles();
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; }
  });

  $('#buildcontext').addEventListener('click', async () => {
    const button = $('#buildcontext');
    const previousText = button.textContent;
    button.disabled = true; button.textContent = 'Building…';
    try {
      const query = $('#contextquery').value.trim();
      const data = await api(`/api/context?query=${encodeURIComponent(query)}&max_chars=24000`);
      $('#contextmeta').textContent = `${data.files_included.length} files · ${Number(data.characters).toLocaleString()} chars / ${Number(data.character_budget).toLocaleString()}`;
      $('#contextpreview').textContent = `${data.note}\n\nIncluded files:\n${data.files_included.map((path) => `• ${path}`).join('\n') || '(none)'}\n\n--- CONTEXT PREVIEW ---\n${data.context}`;
      uiState.dispatch({ type: 'PREPARED_CONTEXT_SET', value: '' });
      $('#context-attachment-indicator').hidden = true;
      $('#usecontext').disabled = !String(data.context || '').trim();
      $('#usecontext').textContent = 'Use in next chat';
      toast('Context pack built locally. Review it, then explicitly attach it to one chat turn.');
    } catch (error) { $('#contextpreview').textContent = error.message; $('#usecontext').disabled = true; toast(error.message); }
    finally { button.disabled = false; button.textContent = previousText; }
  });

  $('#remove-context').addEventListener('click', () => {
    uiState.dispatch({ type: 'PREPARED_CONTEXT_SET', value: '' });
    $('#context-attachment-indicator').hidden = true;
    $('#usecontext').textContent = 'Use in next chat';
    $('#usecontext').disabled = false;
    toast('Workspace context removed.');
  });

  $('#usecontext').addEventListener('click', () => {
    if (uiState.get().preparedContext) {
      uiState.dispatch({ type: 'PREPARED_CONTEXT_SET', value: '' });
      $('#usecontext').textContent = 'Use in next chat';
      $('#context-attachment-indicator').hidden = true;
      toast('Workspace context detached from the next message.');
      return;
    }
    const preview = $('#contextpreview').textContent;
    const marker = '--- CONTEXT PREVIEW ---\n';
    const index = preview.lastIndexOf(marker);
    if (index < 0) { toast('Build a context pack first.'); return; }
    const context = preview.slice(index + marker.length).trim().slice(0, 12000);
    if (!context) { toast('The context pack is empty.'); return; }
    uiState.dispatch({ type: 'PREPARED_CONTEXT_SET', value: context });
    $('#usecontext').textContent = `Attached · ${context.length.toLocaleString()} chars`;
    $('#context-attachment-indicator').hidden = false;
    $('#context-attachment-label').textContent = `Workspace context attached · ${context.length.toLocaleString()} characters (next turn only)`;
    toast(`Context attached to the next chat turn (${context.length.toLocaleString()} characters). It will not be stored in chat history.`);
    showPanel('chat');
    $('#message').focus();
  });

  async function loadActions() {
    try {
      const data = await api('/api/actions');
      $('#count').textContent = data.filter((item) => item.status === 'pending').length;
      const container = $('#actions');
      if (!data.length) {
        container.innerHTML = '<div class="empty">No proposed changes. Agent file edits appear here for review; nothing is written until approved.</div>';
        return;
      }
      container.innerHTML = data.map((item) => {
        const status = String(item.status || 'unknown');
        const actions = status === 'pending'
          ? `<div class="buttons"><button class="btn primary" data-a="${esc(item.id)}" data-d="approve" type="button">Approve & write</button><button class="btn danger" data-a="${esc(item.id)}" data-d="reject" type="button">Reject</button></div>`
          : status === 'approved'
            ? `<div class="buttons"><button class="btn danger" data-a="${esc(item.id)}" data-d="undo" type="button">Undo this change</button></div>` : '';
        const conflict = item.conflict_reason ? `<p class="error-note">${esc(item.conflict_reason)}</p>` : '';
        return `<article class="item"><div class="itemhead"><div><div class="itemtitle">${esc(item.path)}</div><div class="meta2">${esc(item.created_at)} · ${item.overwrites_existing ? 'OVERWRITE PROPOSAL' : 'NEW FILE PROPOSAL'}</div></div><span class="tag ${esc(status)}">${esc(status)}</span></div><p>${esc(item.reason || 'No reason supplied')}</p>${conflict}<div class="diff-label">${item.diff ? 'UNIFIED DIFF · REVIEW BEFORE APPLY' : 'PROPOSED CONTENT'}</div><pre class="content proposal-diff">${esc(item.diff || item.content || '')}</pre>${item.diff ? `<details class="proposal-full-content"><summary>View complete proposed file content</summary><pre class="content">${esc(item.content || '')}</pre></details>` : ''}${item.backup_path ? '<div class="meta2">Verified backup available</div>' : ''}${actions}</article>`;
      }).join('');
      $$('[data-a][data-d]').forEach((button) => button.addEventListener('click', () => actionDecision(button.dataset.a, button.dataset.d, button)));
    } catch (error) { $('#actions').innerHTML = `<div class="empty">${esc(error.message)}</div>`; }
  }

  async function actionDecision(id, decision, button) {
    if (decision === 'approve' && !window.confirm('Apply this exact file proposal?\n\nReview the full content above. Overwrites create a backup, and stale proposals are rejected.')) return;
    if (decision === 'undo' && !window.confirm('Undo this change only if the file has not changed since it was applied? Indra will refuse to overwrite newer work.')) return;
    button.disabled = true;
    try {
      const endpoint = decision === 'undo' ? `/api/actions/${encodeURIComponent(id)}/undo` : `/api/actions/${encodeURIComponent(id)}`;
      const result = await api(endpoint, { method: 'POST', ...(decision === 'undo' ? {} : { body: JSON.stringify({ decision }) }) });
      toast(decision === 'approve' ? `Applied ${result.path}` : decision === 'undo' ? `Undid ${result.path}` : 'Proposal rejected');
      await Promise.all([loadActions(), loadFiles(), loadMetrics()]);
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; }
  }

  async function loadRuns() {
    try {
      const rows = await api('/api/runs');
      const container = $('#runs');
      container.innerHTML = rows.length ? rows.map((run) => {
        const trace = run.trace?.length ? `<details class="trace-details"><summary>Inspect ${run.trace.length} trace events</summary><pre class="content">${esc(run.trace.map((item) => `${item.tool} · ${item.category} · ${item.duration_ms} ms\n${JSON.stringify(item.result)}`).join('\n\n'))}</pre></details>` : '';
        return `<article class="item"><div class="itemhead"><div class="run-heading"><div class="itemtitle">${esc(run.user_message)}</div><div class="meta2">${esc(run.created_at)} · ${esc(run.model)} · ${esc(run.profile || 'balanced')} profile · ${Math.round(run.duration_ms || 0)} ms</div></div><span class="tag ${esc(run.status)}">${esc(run.status)}</span></div><p class="run-answer">${esc(run.answer)}</p><div class="meta2">${run.tool_calls ?? 0} tool calls · ${esc(run.run_id)}</div>${trace}</article>`;
      }).join('') : '<div class="empty">No runs yet. Start a conversation to create your first trace.</div>';
    } catch (error) { $('#runs').innerHTML = `<div class="empty">${esc(error.message)}</div>`; }
  }

  async function loadMetrics() {
    try {
      const data = await api('/api/metrics');
      $('#metric-sample').textContent = data.sample_size;
      $('#metric-success').textContent = data.success_rate === null ? '—' : `${Math.round(data.success_rate * 100)}%`;
      $('#metric-median').textContent = data.median_duration_ms === null ? '—' : `${(data.median_duration_ms / 1000).toFixed(1)}s`;
      $('#metric-tool-errors').textContent = data.tool_error_rate === null ? '—' : `${Math.round(data.tool_error_rate * 100)}%`;
      $('#metrics-note').textContent = data.scope;
    } catch (error) { $('#metrics-note').textContent = `Metrics unavailable: ${error.message}`; }
  }

  async function loadFeedbackSummary() {
    const container = $('#feedback-summary-content');
    const status = $('#feedback-summary-status');
    if (!container || !status) return;
    try {
      const data = await api('/api/feedback');
      const labels = [
        ['useful', 'Useful'], ['incorrect', 'Incorrect'], ['incomplete', 'Incomplete'], ['risky', 'Risky / unsafe'],
      ];
      container.replaceChildren();
      const total = document.createElement('strong');
      total.className = 'feedback-total';
      total.textContent = `${Number(data.total || 0)} ratings`;
      container.append(total);
      const breakdown = document.createElement('div');
      breakdown.className = 'feedback-breakdown-list';
      labels.forEach(([key, label]) => {
        const item = document.createElement('div'); item.className = 'feedback-count';
        const name = document.createElement('span'); name.textContent = label;
        const count = document.createElement('strong'); count.textContent = String(Number(data.counts?.[key] || 0));
        item.append(name, count); breakdown.append(item);
      });
      container.append(breakdown);
      status.textContent = data.total ? `${Number(data.flagged || 0)} ratings marked incorrect, incomplete, or risky. This is self-reported feedback, not an objective success rate.` : 'No rating is required to use Origo. Ratings are optional and can be cleared at any time.';
      const clear = $('#feedback-clear');
      if (clear) clear.disabled = !Number(data.total || 0);
    } catch (error) {
      container.textContent = `Outcome ratings unavailable: ${error.message}`;
      status.textContent = 'Chat and run history remain available without feedback.';
    }
  }

  $('#feedback-clear')?.addEventListener('click', async () => {
    const button = $('#feedback-clear');
    if (!window.confirm('Clear all locally saved outcome ratings? This does not delete runs or conversations.')) return;
    button.disabled = true;
    try {
      const result = await api('/api/feedback', { method: 'DELETE' });
      toast(`Cleared ${Number(result.deleted || 0)} local ratings.`);
      await Promise.all([loadFeedbackSummary(), refreshVisibleFeedback()]);
    } catch (error) {
      toast(`Could not clear ratings: ${error.message}`);
      button.disabled = false;
    }
  });

  async function refreshModelOptions() {
    try {
      const data = await api('/api/models');
      const select = $('#model-select');
      const choices = ['<option value="auto">Auto-detect (first advertised model)</option>'];
      (data.models || []).forEach((model) => choices.push(`<option value="${esc(model)}">${esc(model)}</option>`));
      select.innerHTML = choices.join('');
      select.value = data.configured || 'auto';
      $('#model-help').textContent = data.models?.length
        ? `${data.models.length} model ID(s) advertised by ${data.endpoint || 'the gateway'}. Selection is stored locally.`
        : `No model list received. ${data.error || 'Start llama-swap or llama.cpp, then refresh diagnostics.'}`;
    } catch (error) { $('#model-help').textContent = error.message; }
  }
  $('#save-model').addEventListener('click', async () => {
    const value = $('#model-select').value;
    const button = $('#save-model'); button.disabled = true;
    try {
      const result = await api('/api/model', { method: 'POST', body: JSON.stringify({ model: value }) });
      toast(`Model selection saved: ${result.model}`);
      await refreshStatus();
      await refreshModelOptions();
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; }
  });

  $('#model-smoke').addEventListener('click', async () => {
    const button = $('#model-smoke');
    const output = $('#model-smoke-result');
    button.disabled = true; button.textContent = 'Testing…';
    output.textContent = 'Sending one bounded inference request. This may load the selected model.';
    output.className = 'smoke-result';
    try {
      const data = await api('/api/model/smoke', { method: 'POST', body: '{}' });
      const labels = { passed: 'PASS', partial: 'PARTIAL', failed: 'FAILED', timeout: 'TIMEOUT', unreachable: 'UNREACHABLE' };
      output.textContent = `${labels[data.status] || String(data.status).toUpperCase()} · ${data.model || 'model'} · ${Number(data.duration_ms || 0).toLocaleString()} ms
${data.summary}`;
      output.className = `smoke-result ${data.status === 'passed' ? 'good' : data.status === 'partial' ? 'warn' : 'bad'}`;
      toast(data.status === 'passed' ? 'Model and tool-call probe passed.' : 'Model probe finished; inspect the result.');
    } catch (error) {
      output.textContent = `Test request failed: ${error.message}`;
      output.className = 'smoke-result bad';
      toast(error.message);
    } finally { button.disabled = false; button.textContent = 'Test inference + tool calls'; }
  });

  $('#export-chat').addEventListener('click', async () => {
    if (!uiState.get().conversationId) { toast('Start a saved conversation before exporting.'); return; }
    const button = $('#export-chat'); button.disabled = true;
    try {
      const row = await api(`/api/sessions/${encodeURIComponent(uiState.get().conversationId)}`);
      const workspace = String(row.workspace || '').replaceAll('\\', '/');
      const lines = [`# ${row.title || 'Indra Origo conversation'}`, '', `- Exported: ${new Date().toISOString()}`, `- Workspace: ${workspace}`, ''];
      (row.messages || []).forEach((message) => {
        const role = message.role === 'user' ? 'You' : 'Indra Origo';
        lines.push(`## ${role}`, '', String(message.content || '').replace(/\r\n/g, '\n'), '');
        if (message.run_id || message.status) lines.push(`_Status: ${message.status || 'unknown'}${message.run_id ? ` · Run ${message.run_id}` : ''}_`, '');
      });
      lines.push('---', '', 'Exported locally by Indra Origo. Review project excerpts before sharing.', '');
      const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url; anchor.download = `indra-lok-${String(row.title || 'conversation').replace(/[^a-z0-9_-]+/gi, '-').slice(0, 48) || 'conversation'}.md`;
      document.body.append(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url);
      toast('Conversation exported as Markdown.');
    } catch (error) { toast(`Could not export conversation: ${error.message}`); }
    finally { button.disabled = false; }
  });

  $('#export-data').addEventListener('click', () => {
    if (!window.confirm('Export a local research/debug JSON bundle? It includes saved conversation text, run traces, tool arguments, and possible project excerpts. Review it before sharing.')) return;
    window.location.assign('/api/export');
  });

  function permissionKindLabel(kind) {
    return ({ network: 'EXTERNAL NETWORK ACCESS', sandbox: 'DOCKER SANDBOX EXECUTION', plugin: 'LOCAL PLUGIN CALL' })[kind] || 'CAPABILITY PERMISSION';
  }

  function showPermissionPrompt(permission) {
    if (!permission?.id || activePermissionRequest?.id === permission.id) return;
    // The agent awaits one permission request at a time; never stack overlapping modals.
    activePermissionRequest = permission;
    $('#permission-kind-label').textContent = permissionKindLabel(permission.kind);
    $('#permission-title').textContent = permission.title || 'Indra needs your approval';
    $('#permission-summary-text').textContent = permission.summary || 'The agent requested a sensitive capability.';
    $('#permission-detail-text').textContent = permission.detail || 'No additional details provided.';
    $('#permission-expiry').textContent = `Request expires in about ${Number(permission.expires_in_seconds || 180)} seconds. Approve only this described action.`;
    $('#permission-domain').hidden = !(permission.scope_options || []).includes('domain');
    $('#permission-modal').hidden = false;
    document.body.classList.add('modal-open');
    $('#permission-deny').focus();
    loadPermissions().catch(() => {});
  }

  async function decidePermission(permissionId, decision, scope = 'once') {
    if (permissionDecisionBusy) return;
    permissionDecisionBusy = true;
    ['#permission-deny', '#permission-domain', '#permission-approve'].forEach((selector) => { const button = $(selector); if (button) button.disabled = true; });
    try {
      await api(`/api/permissions/${encodeURIComponent(permissionId)}`, {
        method: 'POST', body: JSON.stringify({ decision, scope })
      });
      if (activePermissionRequest?.id === permissionId) {
        $('#permission-modal').hidden = true;
        document.body.classList.remove('modal-open');
        activePermissionRequest = null;
      }
      toast(decision === 'approve' ? (scope === 'domain' ? 'Host allowed for this session only.' : 'Action approved once.') : 'Action denied. No requested operation was started.');
      await loadPermissions();
    } catch (error) {
      toast(`Could not record permission decision: ${error.message}`);
    } finally {
      permissionDecisionBusy = false;
      ['#permission-deny', '#permission-domain', '#permission-approve'].forEach((selector) => { const button = $(selector); if (button) button.disabled = false; });
    }
  }

  $('#permission-deny').addEventListener('click', () => {
    if (activePermissionRequest) decidePermission(activePermissionRequest.id, 'deny', 'once');
  });
  $('#permission-approve').addEventListener('click', () => {
    if (activePermissionRequest) decidePermission(activePermissionRequest.id, 'approve', 'once');
  });
  $('#permission-domain').addEventListener('click', () => {
    if (activePermissionRequest) decidePermission(activePermissionRequest.id, 'approve', 'domain');
  });

  async function loadPermissions() {
    const pendingBox = $('#pending-permissions');
    if (!pendingBox) return;
    try {
      const [policy, pendingData] = await Promise.all([api('/api/policy'), api('/api/permissions/pending')]);
      $('#network-policy').value = policy.network_policy || 'ask';
      $('#network-policy-badge').textContent = (policy.network_policy || 'ask') === 'ask' ? 'ASK FIRST' : 'BLOCKED';
      $('#docker-sandbox-enabled').checked = !!policy.docker_sandbox_enabled;
      const docker = policy.docker_sandbox || {};
      $('#pull-sandbox-image').disabled = docker.image === 'indra-sandbox:dev';
      $('#pull-sandbox-image').title = docker.image === 'indra-sandbox:dev' ? 'The selected dev image is built locally; use Build dev image or reset to the .env image.' : 'Pull selected image from registry after confirmation';
      $('#docker-policy-badge').textContent = docker.ready ? 'READY' : (policy.docker_sandbox_enabled ? 'ENABLED · NOT READY' : 'OFF');
      $('#docker-policy-summary').textContent = `${docker.ready ? 'READY' : 'NOT READY'}\nCLI: ${docker.docker_available ? 'found' : 'not found'} · daemon: ${docker.daemon_available ? 'online' : 'offline'} · image: ${docker.image_available ? 'present' : 'missing'}\nImage: ${docker.image || 'unknown'}\nNetwork: ${docker.network || 'none'}\n${docker.detail || ''}`;
      const domains = policy.session_allowed_domains || [];
      $('#domain-grants').textContent = domains.length ? `Session-only allowed hosts: ${domains.join(', ')}` : 'No domains granted for this session.';
      const pending = pendingData.pending || [];
      $('#permission-count').textContent = String(pending.length);
      $('#pending-summary').textContent = `${pending.length} WAITING`;
      if (!pending.length) {
        pendingBox.innerHTML = '<div class="empty">No pending permission requests.</div>';
      } else {
        pendingBox.innerHTML = pending.map((item) => {
          const hostButton = (item.scope_options || []).includes('domain')
            ? `<button class="btn" type="button" data-permit-id="${esc(item.id)}" data-decision="approve" data-scope="domain">Allow host this session</button>` : '';
          return `<article class="item permission-pending-item"><div class="itemhead"><div><div class="itemtitle">${esc(item.title || item.tool)}</div><div class="meta2">${esc(item.kind)} · ${esc(item.tool)}${item.host ? ` · ${esc(item.host)}` : ''}</div></div><span class="tag pending">AWAITING</span></div><p>${esc(item.summary || '')}</p><pre class="permission-pending-detail">${esc(item.detail || '')}</pre><div class="permission-actions"><button class="btn danger" type="button" data-permit-id="${esc(item.id)}" data-decision="deny" data-scope="once">Deny</button>${hostButton}<button class="btn primary" type="button" data-permit-id="${esc(item.id)}" data-decision="approve" data-scope="once">Approve once</button></div></article>`;
        }).join('');
        $$('[data-permit-id]').forEach((button) => button.addEventListener('click', () => decidePermission(button.dataset.permitId, button.dataset.decision, button.dataset.scope)));
      }
    } catch (error) {
      $('#docker-policy-summary').textContent = `Could not load permission settings: ${error.message}`;
      pendingBox.innerHTML = `<div class="empty">Permission information unavailable: ${esc(error.message)}</div>`;
    }
  }

  $('#save-network-policy').addEventListener('click', async () => {
    const policy = $('#network-policy').value === 'deny' ? 'deny' : 'ask';
    try {
      await api('/api/policy', { method: 'POST', body: JSON.stringify({ network_policy: policy }) });
      toast(policy === 'ask' ? 'Agent web actions will ask before connecting.' : 'Agent web tools are blocked.');
      await loadPermissions();
    } catch (error) { toast(error.message); }
  });
  $('#clear-domain-grants').addEventListener('click', async () => {
    try {
      await api('/api/policy', { method: 'POST', body: JSON.stringify({ clear_session_grants: true }) });
      toast('Session host grants cleared.'); await loadPermissions();
    } catch (error) { toast(error.message); }
  });
  $('#docker-sandbox-enabled').addEventListener('change', async () => {
    const enabled = $('#docker-sandbox-enabled').checked;
    try {
      await api('/api/policy', { method: 'POST', body: JSON.stringify({ docker_sandbox_enabled: enabled }) });
      toast(enabled ? 'Docker capability enabled. Commands still require per-action approval.' : 'Docker capability disabled.');
      await Promise.all([loadPermissions(), loadExtensions()]);
    } catch (error) {
      $('#docker-sandbox-enabled').checked = !enabled;
      toast(error.message);
    }
  });
  $('#refresh-permissions').addEventListener('click', loadPermissions);
  $('#build-sandbox-image').addEventListener('click', async () => {
    if (!window.confirm('Build the reviewed indra-sandbox:dev image using Docker?\n\nThis is a HOST-SIDE Docker build, not a sandboxed command. Docker will download the python:3.12-slim base image and install OS/Python packages from configured registries. The build context is only the project docker/ folder; the workspace, data/, and .env are not sent. Review docker/Dockerfile.dev-sandbox before continuing.\n\nOnly continue if you trust Docker Desktop and the configured package registries.')) return;
    const button = $('#build-sandbox-image'); const summary = $('#docker-policy-summary');
    button.disabled = true; button.textContent = 'Building image…';
    summary.textContent = 'Building reviewed Dockerfile. This may take several minutes and requires registry access…';
    try {
      const result = await api('/api/sandbox/build-image', { method: 'POST', body: JSON.stringify({ confirmed: true }) });
      if (result.status === 'built') {
        toast('Dev sandbox image built and selected.');
        await Promise.all([loadPermissions(), loadExtensions()]);
        summary.textContent += `\n\nLAST BUILD · BUILT · ${result.image}\nSelected as the active sandbox image and saved locally.\n${result.output || ''}`;
      } else {
        summary.textContent = `${result.error || 'Image build failed.'}\n${result.output || ''}`;
        toast('Docker image build failed; inspect the output above.');
      }
    } catch (error) { summary.textContent = `Image build failed: ${error.message}`; toast(error.message); }
    finally { button.disabled = false; button.textContent = 'Build dev image…'; }
  });
  $('#reset-sandbox-image').addEventListener('click', async () => {
    if (!window.confirm('Use INDRA_SANDBOX_IMAGE from .env again? This changes the selected image for future sandbox runs.')) return;
    try {
      await api('/api/policy', { method: 'POST', body: JSON.stringify({ reset_sandbox_image: true }) });
      toast('Sandbox image selection reset to .env.'); await Promise.all([loadPermissions(), loadExtensions()]);
    } catch (error) { toast(error.message); }
  });
  $('#pull-sandbox-image').addEventListener('click', async () => {
    const policy = await api('/api/policy').catch(() => null);
    const image = policy?.docker_sandbox?.image || 'python:3.12-slim';
    if (!window.confirm(`Download Docker image “${image}” from the configured container registry?\n\nThis is a host-side network operation, separate from sandboxed commands. Review the image source before continuing.`)) return;
    const button = $('#pull-sandbox-image'); button.disabled = true; button.textContent = 'Pulling image…';
    try {
      const result = await api('/api/sandbox/pull-image', { method: 'POST', body: JSON.stringify({ confirmed: true }) });
      const summary = $('#docker-policy-summary');
      toast('Sandbox image downloaded.');
      await Promise.all([loadPermissions(), loadExtensions()]);
      summary.textContent += `\n\nLAST PULL · ${result.status.toUpperCase()} · ${result.image}\n${result.output || ''}`;
    } catch (error) { $('#docker-policy-summary').textContent = error.message; toast(error.message); }
    finally { button.disabled = false; button.textContent = 'Pull sandbox image…'; }
  });

  async function loadCapabilities() {
    const output = $('#capabilities-output');
    if (!output) return;
    output.textContent = 'Reading implementation-level capabilities…';
    try {
      const data = await api('/api/capabilities');
      const lines = [
        `Provider: ${data.provider.protocol} · ${data.provider.endpoint}`,
        `Endpoint classified as: ${data.provider.local_endpoint ? 'loopback/local' : 'non-loopback/hosted or remote'}`,
        '', 'TRANSPORT',
        ...Object.entries(data.transport || {}).map(([name, status]) => `${name}: ${status}`),
        '', 'MODALITIES',
        ...Object.entries(data.modalities || {}).map(([name, info]) => `${name}: ${info.status}${info.ocr ? ` · OCR ${info.ocr}` : ''}${info.api ? ` · ${info.api}` : ''}${info.note ? ` — ${info.note}` : ''}`),
        '', `Limits: ${data.limits.max_attachments} files · ${Math.round(data.limits.max_file_bytes/1024/1024)} MiB/file · ${Math.round(data.limits.max_total_binary_bytes/1024/1024)} MiB combined binary`,
        '', data.provider_claims || 'Provider-specific capabilities have not been verified.'
      ];
      output.textContent = lines.join('\n');
    } catch (error) { output.textContent = `Capability inventory unavailable: ${error.message}`; }
  }
  $('#capability-refresh')?.addEventListener('click', loadCapabilities);

  async function runScout() {
    const button = $('#run-scout');
    const summary = $('#scout-summary');
    const results = $('#scout-results');
    if (!button || !summary || !results) return;
    button.disabled = true;
    button.textContent = 'Scout is checking…';
    summary.textContent = 'Running bounded read-only checks. No inference calls will be made.';
    results.replaceChildren();
    try {
      const report = await api('/api/scout/run', { method: 'POST', body: '{}' });
      const counts = report.summary || {};
      summary.textContent = `${String(report.status || 'unknown').toUpperCase()} · ${counts.passed || 0} passed · ${counts.warnings || 0} warnings · ${counts.failed || 0} failed · ${counts.total || 0} checks`;
      const contract = document.createElement('div');
      contract.className = 'scout-contract';
      contract.textContent = `SAFETY: model inference ${report.safety_contract?.model_inference ? 'enabled' : 'not called'} · outbound network ${report.safety_contract?.outbound_network ? 'enabled' : 'not used'} · writes ${report.safety_contract?.writes ? 'enabled' : 'not performed'} · approvals ${report.safety_contract?.approvals_granted ? 'granted' : 'untouched'}`;
      results.append(contract);
      for (const check of (report.checks || [])) {
        const row = document.createElement('article'); row.className = 'scout-check';
        const mark = document.createElement('span'); mark.className = `scout-mark ${check.status || 'warn'}`;
        mark.textContent = check.status === 'pass' ? '✓' : check.status === 'fail' ? '!' : '·';
        const detail = document.createElement('div');
        const title = document.createElement('b'); title.textContent = check.name || check.id || 'Unnamed check';
        const evidence = document.createElement('small'); evidence.textContent = check.evidence || 'No evidence supplied.';
        detail.append(title, evidence); row.append(mark, detail); results.append(row);
      }
      if (!(report.checks || []).length) { const empty = document.createElement('div'); empty.className='empty'; empty.textContent='Scout returned no individual checks.'; results.append(empty); }
      toast(report.status === 'pass' ? 'Scout checks completed.' : 'Scout completed; review the findings.');
    } catch (error) {
      summary.textContent = `Scout could not complete: ${error.message}`;
      const empty = document.createElement('div'); empty.className='empty'; empty.textContent='The self-test request failed before a report was received.'; results.append(empty);
    } finally { button.disabled = false; button.textContent = 'Run read-only self-test'; }
  }
  $('#run-scout')?.addEventListener('click', runScout);

  async function runHmiAudit() {
    const button = $('#run-hmi-audit');
    const summary = $('#hmi-audit-summary');
    const results = $('#hmi-audit-results');
    if (!button || !summary || !results) return;
    button.disabled = true;
    button.textContent = 'Reviewing…';
    summary.textContent = 'Inspecting local frontend source. No model or external service is called.';
    results.replaceChildren();
    try {
      const report = await api('/api/hmi/audit');
      const counts = report.summary || {};
      summary.textContent = `${String(report.status || 'unknown').toUpperCase()} · ${counts.passed || 0} passed · ${counts.warnings || 0} warnings · ${counts.failed || 0} failed · ${counts.total || 0} heuristics`;
      for (const check of (report.checks || [])) {
        const row = document.createElement('article'); row.className = 'hmi-audit-row';
        const mark = document.createElement('span'); mark.className = `hmi-audit-mark ${check.status || 'warn'}`;
        mark.textContent = check.status === 'pass' ? '✓' : check.status === 'fail' ? '!' : '·';
        const detail = document.createElement('div');
        const title = document.createElement('b'); title.textContent = check.name || check.id || 'Unnamed heuristic';
        const evidence = document.createElement('small'); evidence.textContent = check.evidence || 'No evidence supplied.';
        detail.append(title, evidence);
        const category = document.createElement('span'); category.className = 'hmi-category'; category.textContent = check.category || 'general';
        row.append(mark, detail, category); results.append(row);
      }
      for (const limitation of (report.limitations || [])) {
        const row = document.createElement('article'); row.className = 'hmi-audit-row';
        const icon = document.createElement('span'); icon.className = 'hmi-audit-mark warn'; icon.textContent = 'i';
        const text = document.createElement('small'); text.textContent = limitation;
        row.append(icon, text); results.append(row);
      }
      toast(report.status === 'pass' ? 'HMI quality gate passed its static checks.' : 'HMI review complete; inspect findings and limitations.');
    } catch (error) {
      summary.textContent = `HMI review unavailable: ${error.message}`;
      const empty = document.createElement('div'); empty.className = 'empty'; empty.textContent = 'Unable to retrieve the static HMI report.'; results.append(empty);
    } finally { button.disabled = false; button.textContent = 'Review interface'; }
  }
  $('#run-hmi-audit')?.addEventListener('click', runHmiAudit);

  function appendEvidenceRow(container, titleText, detailText, status = 'info') {
    const row = document.createElement('article'); row.className = 'hmi-audit-row';
    const mark = document.createElement('span'); mark.className = `hmi-audit-mark ${status}`; mark.textContent = status === 'pass' ? '✓' : status === 'fail' ? '!' : '·';
    const detail = document.createElement('div');
    const title = document.createElement('b'); title.textContent = titleText;
    const meta = document.createElement('small'); meta.textContent = detailText;
    detail.append(title, meta); row.append(mark, detail); container.append(row);
    return row;
  }

  async function refreshCapsules() {
    const container = $('#capsule-results');
    if (!container) return;
    try {
      const data = await api('/api/capsules');
      container.replaceChildren();
      const fingerprint = document.createElement('p'); fingerprint.className = 'helptext';
      fingerprint.textContent = `This installation signer fingerprint (SHA-256): ${data.signer_fingerprint_sha256 || 'unavailable'}`;
      container.append(fingerprint);
      if (!(data.capsules || []).length) {
        const empty = document.createElement('div'); empty.className = 'empty'; empty.textContent = 'No signed Capsules yet.'; container.append(empty); return;
      }
      for (const capsule of data.capsules) {
        const row = document.createElement('article'); row.className = 'scout-check';
        const mark = document.createElement('span'); mark.className = 'scout-mark pass'; mark.textContent = '◇';
        const detail = document.createElement('div');
        const title = document.createElement('b'); title.textContent = `${capsule.capsule_id} · ${capsule.file_count} selected files`;
        const meta = document.createElement('small'); meta.textContent = `${capsule.created_at || 'Time unavailable'} · ${Math.round((capsule.size_bytes || 0) / 1024)} KiB · signer ${String(capsule.fingerprint_sha256 || '').slice(0, 16)}…`;
        const actions = document.createElement('div'); actions.className = 'evidence-actions';
        const verify = document.createElement('button'); verify.type = 'button'; verify.className = 'btn'; verify.textContent = 'Verify integrity';
        verify.addEventListener('click', async () => {
          verify.disabled = true; verify.textContent = 'Verifying…';
          try {
            const report = await api(`/api/capsules/${encodeURIComponent(capsule.capsule_id)}/verify`, { method: 'POST', body: '{}' });
            appendEvidenceRow(actions, report.valid ? 'Integrity verified' : 'Verification failed', `${report.signature_valid ? 'Signature valid' : 'Signature invalid'} · ${report.files_valid ? 'files match manifest' : (report.problems || []).join(', ')} · ${report.signer_trusted_by_this_install ? 'trusted by this install' : 'signer not pinned/trusted by this install'}`, report.valid ? 'pass' : 'fail');
          } catch (error) { appendEvidenceRow(actions, 'Verification request failed', error.message, 'fail'); }
          finally { verify.disabled = false; verify.textContent = 'Verify integrity'; }
        });
        const receipt = document.createElement('a'); receipt.className = 'btn'; receipt.href = `/api/capsules/${encodeURIComponent(capsule.capsule_id)}/receipt`; receipt.textContent = 'Integrity receipt'; receipt.setAttribute('download', `${capsule.capsule_id}-receipt.html`);
        const link = document.createElement('a'); link.className = 'btn'; link.href = capsule.download_url; link.textContent = 'Download ZIP'; link.setAttribute('download', `${capsule.capsule_id}.zip`);
        actions.append(verify, receipt, link); detail.append(title, meta, actions); row.append(mark, detail); container.append(row);
      }
    } catch (error) {
      container.replaceChildren(); const empty = document.createElement('div'); empty.className = 'empty'; empty.textContent = `Capsule inventory unavailable: ${error.message}`; container.append(empty);
    }
  }

  $('#refresh-capsules')?.addEventListener('click', refreshCapsules);
  $('#create-capsule')?.addEventListener('click', async () => {
    const button = $('#create-capsule'); const summary = $('#capsule-summary');
    button.disabled = true; summary.textContent = 'Creating a passive signed archive. No code will be executed.';
    try {
      const paths = ($('#capsule-paths').value || '').split(/[\n,]/).map(value => value.trim()).filter(Boolean);
      const runId = ($('#capsule-run-id').value || '').trim();
      const created = await api('/api/capsules', { method: 'POST', body: JSON.stringify({ run_id: runId || null, workspace_paths: paths, include_recent_event_metadata: true }) });
      summary.textContent = `Created ${created.capsule_id} · ${created.file_count} selected files · ${Math.round(created.size_bytes / 1024)} KiB. Keep signer fingerprint ${created.fingerprint_sha256}.`;
      await refreshCapsules(); toast('Signed Capsule created.');
    } catch (error) { summary.textContent = `Capsule creation blocked: ${error.message}`; }
    finally { button.disabled = false; }
  });

  async function refreshProofLedger() {
    const container = $('#proof-ledger-results'); const summary = $('#proof-ledger-summary');
    if (!container || !summary) return;
    try {
      const data = await api('/api/proof/ledger'); container.replaceChildren();
      const evidenceRows = data.evidence || []; const claims = data.claims || [];
      summary.textContent = `${evidenceRows.length} recent evidence records · ${claims.length} recent claims · local-only registry`;
      for (const item of evidenceRows.slice().reverse()) {
        appendEvidenceRow(container, `Evidence ${item.evidence_id}`, `${item.path} · SHA-256 ${String(item.source_sha256 || '').slice(0, 16)}… · ${item.scope || ''}`, 'info');
      }
      for (const item of claims.slice().reverse()) {
        const status = item.status === 'reviewed_by_human' ? 'pass' : ['unsupported','numeric_mismatch','stale_evidence'].includes(item.status) ? 'fail' : 'warn';
        appendEvidenceRow(container, `${item.status}: ${item.statement}`, `Claim ID ${item.claim_id} · evidence ${item.evidence_ids?.join(', ') || 'none'} · ${item.limitation || ''}`, status);
      }
      if (!evidenceRows.length && !claims.length) { const empty = document.createElement('div'); empty.className = 'empty'; empty.textContent = 'No evidence or claims registered yet.'; container.append(empty); }
    } catch (error) { summary.textContent = `Proof Ledger unavailable: ${error.message}`; }
  }
  $('#refresh-proof-ledger')?.addEventListener('click', refreshProofLedger);

  $('#add-proof-evidence')?.addEventListener('click', async () => {
    const button = $('#add-proof-evidence'); const summary = $('#proof-evidence-summary');
    button.disabled = true; summary.textContent = 'Checking the exact excerpt against the local file…';
    try {
      const item = await api('/api/proof/evidence', { method: 'POST', body: JSON.stringify({ path: $('#proof-evidence-path').value.trim(), excerpt: $('#proof-evidence-excerpt').value, note: $('#proof-evidence-note').value }) });
      const ids = ($('#proof-claim-evidence-ids').value || '').split(',').map(x => x.trim()).filter(Boolean);
      if (!ids.includes(item.evidence_id)) ids.push(item.evidence_id);
      $('#proof-claim-evidence-ids').value = ids.join(', ');
      summary.textContent = `Evidence registered: ${item.evidence_id}. The file hash is ${item.source_sha256.slice(0, 16)}…`;
      await refreshProofLedger(); toast('Evidence excerpt registered.');
    } catch (error) { summary.textContent = `Evidence was not registered: ${error.message}`; }
    finally { button.disabled = false; }
  });

  $('#add-proof-claim')?.addEventListener('click', async () => {
    const button = $('#add-proof-claim'); button.disabled = true;
    try {
      const evidenceIds = ($('#proof-claim-evidence-ids').value || '').split(',').map(x => x.trim()).filter(Boolean);
      const claim = await api('/api/proof/claims', { method: 'POST', body: JSON.stringify({ statement: $('#proof-claim-statement').value, evidence_ids: evidenceIds }) });
      $('#proof-review-claim-id').value = claim.claim_id;
      $('#proof-lint-text').value = $('#proof-claim-statement').value;
      $('#proof-lint-summary').textContent = `Claim registered as ${claim.status}. It remains blocked/review-required until evidence and review criteria are satisfied.`;
      await refreshProofLedger(); toast('Claim registered in the Proof Ledger.');
    } catch (error) { $('#proof-lint-summary').textContent = `Claim was not registered: ${error.message}`; }
    finally { button.disabled = false; }
  });

  $('#lint-proof-text')?.addEventListener('click', async () => {
    const button = $('#lint-proof-text'); const summary = $('#proof-lint-summary'); button.disabled = true;
    try {
      const report = await api('/api/proof/lint', { method: 'POST', body: JSON.stringify({ text: $('#proof-lint-text').value, claim_ids: null }) });
      summary.textContent = `${String(report.status).toUpperCase()} · ${report.summary.claims_checked} registered claims checked · ${report.summary.flagged} flagged · preflight ${report.export_allowed ? 'clear for registered claims' : 'BLOCKED / REVIEW REQUIRED'} (not a global exporter gate).`;
      const container = $('#proof-ledger-results');
      const section = document.createElement('div'); section.className = 'proof-lint-report';
      appendEvidenceRow(section, 'Draft lint report', 'Only registered claims are checked; the linter does not discover every claim in arbitrary prose.', report.export_allowed ? 'pass' : 'warn');
      for (const item of report.findings || []) appendEvidenceRow(section, `${item.status}: ${item.statement}`, `Included in text: ${item.included_in_text ? 'yes' : 'no'} · evidence: ${item.evidence_ids.join(', ') || 'none'}`, ['reviewed_by_human'].includes(item.status) ? 'pass' : 'fail');
      container.prepend(section);
    } catch (error) { summary.textContent = `Draft lint failed: ${error.message}`; }
    finally { button.disabled = false; }
  });

  $('#review-proof-claim')?.addEventListener('click', async () => {
    const id = $('#proof-review-claim-id').value.trim(); const summary = $('#proof-lint-summary'); const button = $('#review-proof-claim');
    button.disabled = true;
    try {
      const item = await api(`/api/proof/claims/${encodeURIComponent(id)}/review`, { method: 'POST', body: JSON.stringify({ reviewed: true }) });
      summary.textContent = `Marked ${item.claim_id} reviewed by you. This is an attestation—not proof of truth. Re-run lint before using the draft.`;
      await refreshProofLedger(); toast('Manual review recorded.');
    } catch (error) { summary.textContent = `Review not accepted: ${error.message}`; }
    finally { button.disabled = false; }
  });

  async function loadDiagnostics() {
    loadCapabilities().catch(() => {});
    const container = $('#diagnostics');
    $('#diagsummary').textContent = 'Checking local endpoints…';
    container.innerHTML = '<div class="empty">Checking local endpoints…</div>';
    try {
      const data = await api('/api/doctor');
      $('#diagsummary').textContent = `${data.summary.online} online · ${data.summary.reachable} reachable · ${data.summary.offline} offline`;
      const services = (data.services || []).map((service) => {
        const state = String(service.state || 'unknown');
        const statusClass = state === 'online' ? 'approved' : state === 'reachable' ? 'pending' : 'rejected';
        return `<article class="item diag-item"><div class="itemhead"><div><div class="itemtitle">${esc(service.name.replaceAll('_', ' '))}</div><div class="meta2">${esc(service.url || 'Not configured')} · ${service.latency_ms == null ? '—' : `${service.latency_ms} ms`}</div></div><span class="tag ${statusClass}">${esc(state)}</span></div><p>${esc(service.detail)}</p>${service.models?.length ? `<p class="meta2">Advertised models: ${esc(service.models.join(', '))}</p>` : ''}</article>`;
      }).join('');
      const qdrant = data.integrations?.qdrant || {};
      const workbench = data.integrations?.workbench_api || {};
      const knowledge = data.integrations?.knowledge_search || {};
      const localRag = data.integrations?.local_rag || {};
      container.innerHTML = services
        + `<article class="item diag-item"><div class="itemtitle">Qdrant metadata</div><p>${esc(qdrant.detail || 'Unavailable')} · ${qdrant.collection_count ?? 0} collections</p>${qdrant.collections?.length ? `<p class="meta2">${esc(qdrant.collections.join(', '))}</p>` : ''}</article>`
        + `<article class="item diag-item"><div class="itemtitle">Local RAG · ${Number(localRag.documents || 0)} documents / ${Number(localRag.chunks || 0)} chunks</div><p>${esc(localRag.privacy_note || 'Local SQLite/FTS5 retrieval is available in Knowledge Studio.')}</p><p class="meta2">${esc(localRag.storage || 'SQLite + FTS5')} · ${localRag.semantic_search_active ? `semantic vectors active (${esc(localRag.embedding_model || 'configured model')})` : 'lexical retrieval available'} · ${Number(localRag.compatible_embedded_chunks || 0)} compatible embedding chunks</p></article>`
        + `<article class="item diag-item"><div class="itemtitle">Legacy Qdrant retrieval · ${knowledge.enabled ? 'configured' : 'disabled'}</div><p>${esc(knowledge.detail || 'Unavailable')}</p><p class="meta2">${esc(knowledge.collection || 'No collection')} · ${esc(knowledge.embedding_model || 'No embedding model')} · ${esc(knowledge.embedding_endpoint || 'No embedding endpoint')}</p></article>`
        + `<article class="item diag-item"><div class="itemtitle">Workbench API schema</div><p>${esc(workbench.detail || 'Unavailable')} · ${workbench.path_count ?? 0} paths / ${workbench.operation_count ?? 0} operations</p>${workbench.paths?.length ? `<p class="meta2">${esc(workbench.paths.join(', '))}</p>` : ''}</article>`;
      await refreshModelOptions();
    } catch (error) {
      $('#diagsummary').textContent = 'Diagnostic request failed';
      container.innerHTML = `<div class="empty">${esc(error.message)}</div>`;
    }
  }
  $('#diagrefresh').addEventListener('click', loadDiagnostics);
  $('#refresh').addEventListener('click', async () => {
    await refreshStatus();
    await Promise.all([loadActions(), loadMetrics()]);
    if ($('#p-diagnostics').classList.contains('active')) await loadDiagnostics();
    toast('Workstation status refreshed.');
  });

  async function loadExtensions() {
    const skillsBox = $('#skills-list');
    const pluginsBox = $('#plugins-list');
    skillsBox.innerHTML = '<div class="empty">Refreshing skills and plugins…</div>';
    try {
      extensionData = await api('/api/extensions');
      const skills = extensionData.skills || [];
      skillsBox.replaceChildren();
      if (!skills.length) skillsBox.innerHTML = '<div class="empty">No SKILL.md files found in the skills folder.</div>';
      skills.forEach((skill) => {
        const row = document.createElement('div');
        row.className = 'extension-row';
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox'; checkbox.checked = uiState.get().selectedSkills.includes(skill.id);
        checkbox.setAttribute('aria-label', `Use skill ${skill.name}`);
        checkbox.addEventListener('change', () => {
          if (checkbox.checked && uiState.get().selectedSkills.length >= 6) { checkbox.checked = false; toast('At most six skills can be selected.'); return; }
          const nextSkills = checkbox.checked ? [...new Set([...uiState.get().selectedSkills, skill.id])] : uiState.get().selectedSkills.filter((id) => id !== skill.id);
          uiState.dispatch({ type: 'SKILLS_SET', skills: nextSkills });
          state.textContent = checkbox.checked ? 'SELECTED' : 'AVAILABLE'; state.classList.toggle('on', checkbox.checked);
          toast(checkbox.checked ? `${skill.name} selected for chat.` : `${skill.name} removed from chat skills.`);
        });
        const main = document.createElement('div'); main.className = 'extension-row-main';
        const title = document.createElement('b'); title.textContent = skill.name;
        const description = document.createElement('p'); description.textContent = `${skill.description} · ${skill.bytes} bytes · ${skill.id}`;
        main.append(title, description);
        const actions = document.createElement('div'); actions.className = 'extension-actions';
        const state = document.createElement('span'); state.className = `extension-state ${uiState.get().selectedSkills.includes(skill.id) ? 'on' : ''}`; state.textContent = uiState.get().selectedSkills.includes(skill.id) ? 'SELECTED' : 'AVAILABLE';
        const view = document.createElement('button'); view.type = 'button'; view.textContent = 'View';
        view.addEventListener('click', async () => {
          const target = $('#skill-preview'); target.hidden = false; target.textContent = `Loading ${skill.name}…`;
          try { const detail = await api(`/api/skills/${encodeURIComponent(skill.id)}`); target.textContent = `# ${detail.name}\nID: ${detail.id}\nDescription: ${detail.description}\n\n${detail.content}`; }
          catch (error) { target.textContent = error.message; }
        });
        actions.append(state, view); row.append(checkbox, main, actions); skillsBox.append(row);
      });
      pluginsBox.replaceChildren();
      const plugins = extensionData.plugins || [];
      $('#plugin-summary').textContent = `${plugins.filter((p) => p.enabled).length} ENABLED / ${plugins.length} FOUND`;
      if (!plugins.length) pluginsBox.innerHTML = '<div class="empty">No plugin manifests found.</div>';
      plugins.forEach((plugin) => {
        const row = document.createElement('div'); row.className = 'extension-row';
        const main = document.createElement('div'); main.className = 'extension-row-main';
        const title = document.createElement('b'); title.textContent = `${plugin.name} · v${plugin.version}`;
        const description = document.createElement('p');
        const toolNames = (plugin.tools || []).map((tool) => tool.name).join(', ') || 'No valid tool schemas';
        description.textContent = `${plugin.description || 'No description'} · tools: ${toolNames}`;
        main.append(title, description);
        const state = document.createElement('span'); state.className = `extension-state ${plugin.enabled ? 'on' : ''}`;
        state.textContent = plugin.enabled ? 'ENABLED' : plugin.requested_enabled ? 'GLOBAL GATE OFF' : 'DISABLED';
        row.append(main, state); pluginsBox.append(row);
      });
      const sandbox = extensionData.sandbox || {};
      $('#sandbox-badge').textContent = sandbox.ready ? 'READY' : 'DISABLED';
      const limits = sandbox.limits || {};
      $('#sandbox-summary').textContent = `${sandbox.ready ? 'READY' : 'NOT READY'}\nDocker CLI: ${sandbox.docker_available ? 'found' : 'not found'}\nEnabled: ${sandbox.enabled ? 'yes' : 'no'}\nImage: ${sandbox.image || 'unknown'}\nNetwork: ${sandbox.network || 'none'}\nLimits: ${limits.memory || 'configured RAM'} · ${limits.cpus ?? 'configured CPUs'} CPU · ${limits.pids ?? 'configured PID'} PIDs · ${limits.timeout_seconds || 45}s\nWorkspace tmpfs: ${limits.max_sandbox_workspace_bytes ? `${Math.round(limits.max_sandbox_workspace_bytes / 1048576)} MiB` : 'configured'}\n${sandbox.detail || ''}`;
      $('#sandbox-run-button').disabled = !sandbox.ready;
      const web = extensionData.web || {};
      $('#web-result').textContent = `Ready · cached pages ${web.cached_pages ?? 0}/${web.max_cached_pages ?? 80} · max response ${Number(web.max_response_bytes || 0).toLocaleString()} bytes · per-host interval ${web.per_host_min_interval_seconds || '1.0'} s`;
    } catch (error) {
      skillsBox.textContent = `Could not load extension registry: ${error.message}`;
      pluginsBox.textContent = 'Plugin registry unavailable.';
      $('#sandbox-summary').textContent = error.message;
    }
  }

  $('#extensions-refresh').addEventListener('click', async () => {
    try { await api('/api/extensions/reload', { method: 'POST', body: '{}' }); await loadExtensions(); toast('Skills and plugin registry refreshed.'); }
    catch (error) { toast(error.message); }
  });

  $('#task-graph-run').addEventListener('click', async () => {
    let tasks;
    try { tasks = JSON.parse($('#task-graph-json').value); }
    catch { toast('Task graph must be valid JSON.'); return; }
    if (!Array.isArray(tasks) || tasks.length < 1 || tasks.length > 6) { toast('Task graph requires 1–6 task nodes.'); return; }
    if (!window.confirm(`Run ${tasks.length} model-backed child tasks? Independent nodes can run concurrently; this may use your configured model/provider.`)) return;
    const button = $('#task-graph-run'); const output = $('#task-graph-result');
    button.disabled = true; output.textContent = 'Validating graph, scheduling independent nodes, and running bounded read-only child agents…';
    try {
      const result = await api('/api/task-graph', { method: 'POST', body: JSON.stringify({ tasks, max_concurrency: 2, skills: uiState.get().selectedSkills }) });
      output.textContent = JSON.stringify(result, null, 2);
      toast(`Task graph finished: ${result.completed ?? 0}/${result.task_count ?? tasks.length} completed.`);
    } catch (error) { output.textContent = `Task graph failed: ${error.message}`; }
    finally { button.disabled = false; }
  });

  $('#web-search-button').addEventListener('click', async () => {
    const query = $('#web-query').value.trim(); if (!query) { toast('Enter a web-search query.'); return; }
    if (!window.confirm(`External network request\n\nSend this query to the configured public search provider?\n\n${query.slice(0, 1200)}\n\nThe query leaves this machine. Do not include secrets, private data, or credentials.`)) return;
    const output = $('#web-result'); output.textContent = 'Searching the public web…';
    $('#web-search-button').disabled = true;
    try { output.textContent = JSON.stringify(await api('/api/web/search', { method: 'POST', body: JSON.stringify({ query, limit: 5 }) }), null, 2); }
    catch (error) { output.textContent = `Search failed: ${error.message}`; }
    finally { $('#web-search-button').disabled = false; }
  });
  $('#web-research-button').addEventListener('click', async () => {
    const query = $('#web-query').value.trim(); if (!query) { toast('Enter a research query.'); return; }
    if (!window.confirm(`External research request\n\nSend this query to the configured search provider, then fetch up to three public source pages?\n\n${query.slice(0, 1200)}\n\nFetched pages may contain prompt-injection text and are untrusted evidence. Do not include secrets.`)) return;
    const output = $('#web-result'); output.textContent = 'Searching, checking robots.txt and fetching bounded sources…';
    const buttons = [$('#web-search-button'), $('#web-research-button'), $('#web-fetch-button'), $('#web-crawl-button')];
    buttons.forEach((button) => { button.disabled = true; });
    try { output.textContent = JSON.stringify(await api('/api/web/research', { method: 'POST', body: JSON.stringify({ query, max_pages: 3, max_chars: 9000 }) }), null, 2); }
    catch (error) { output.textContent = `Research failed: ${error.message}`; }
    finally { buttons.forEach((button) => { button.disabled = false; }); }
  });

  $('#web-fetch-button').addEventListener('click', async () => {
    const url = $('#web-url').value.trim(); if (!url) { toast('Enter a public HTTPS page URL.'); return; }
    let hostname = 'unparsed host'; try { hostname = new URL(url).hostname; } catch {}
    if (!window.confirm(`External network request\n\nFetch public page from: ${hostname}\n\nURL: ${url.slice(0, 1800)}\n\nThe request goes to that website. Query parameters may contain private tokens; the harness hides them in approval logs but you should remove them from the URL. Extracted page content is untrusted.`)) return;
    const output = $('#web-result'); output.textContent = 'Fetching and extracting the public page…';
    $('#web-fetch-button').disabled = true;
    try { output.textContent = JSON.stringify(await api('/api/web/fetch', { method: 'POST', body: JSON.stringify({ url, max_chars: 12000 }) }), null, 2); }
    catch (error) { output.textContent = `Fetch failed: ${error.message}`; }
    finally { $('#web-fetch-button').disabled = false; }
  });
  $('#web-crawl-button').addEventListener('click', async () => {
    const url = $('#web-url').value.trim(); if (!url) { toast('Enter a public HTTPS starting URL.'); return; }
    if (!window.confirm('Crawl at most five public static pages on this exact hostname? robots.txt is respected by default.')) return;
    const output = $('#web-result'); output.textContent = 'Crawling same-host pages under page/character budgets…';
    const buttons = [$('#web-search-button'), $('#web-research-button'), $('#web-fetch-button'), $('#web-crawl-button')];
    buttons.forEach((button) => { button.disabled = true; });
    try { output.textContent = JSON.stringify(await api('/api/web/crawl', { method: 'POST', body: JSON.stringify({ url, max_pages: 4, max_chars: 10000 }) }), null, 2); }
    catch (error) { output.textContent = `Crawl failed: ${error.message}`; }
    finally { buttons.forEach((button) => { button.disabled = false; }); }
  });

  function renderSandboxProposalChoices(result) {
    const panel = $('#sandbox-propose-ui');
    const allowed = new Set(result?.proposable_files || []);
    const candidates = (result?.changed_files || []).filter((row) => allowed.has(row.path) && row.proposable === true);
    lastSandboxRunId = candidates.length ? (result.sandbox_run_id || null) : null;
    lastSandboxProposablePaths = candidates.map((row) => row.path);
    panel.hidden = !candidates.length || !lastSandboxRunId;
    if (!candidates.length) { $('#sandbox-propose-list').replaceChildren(); return; }
    $('#sandbox-propose-list').innerHTML = candidates.map((row) => `
      <label class="sandbox-propose-row"><input type="checkbox" checked data-sandbox-path="${esc(row.path)}">
        <span><b>${esc(row.path)}</b><small>${Number(row.bytes || 0).toLocaleString()} bytes · sanitized text file</small></span>
      </label>`).join('');
    $('#sandbox-propose-button').disabled = false;
  }

  $('#sandbox-run-button').addEventListener('click', async () => {
    let command;
    try { command = JSON.parse($('#sandbox-command').value); }
    catch { toast('Enter a valid JSON array of command arguments.'); return; }
    if (!Array.isArray(command) || !command.length || command.length > 24 || command.some((part) => typeof part !== 'string' || !part.length)) {
      toast('Command must be a non-empty JSON array of strings (maximum 24 args); shell strings are blocked.'); return;
    }
    const networkAccess = $('#sandbox-network-access').checked;
    const commandPreview = JSON.stringify(command);
    const confirmation = networkAccess
      ? `HIGH-RISK NETWORK APPROVAL\n\nRun this command in a disposable Docker container WITH general outbound bridge networking?\n\nCommand:\n${commandPreview}\n\nThe container can reach any network destination Docker allows. This is NOT domain-filtered; package scripts may send data outside your machine. The host workspace is not mounted and changes will not be copied back automatically.\n\nOnly continue if you understand and trust this command.`
      : `Run this command inside Docker using a sanitized disposable workspace copy with networking disabled?\n\nCommand:\n${commandPreview}\n\nChanges will not be copied back automatically.`;
    if (!window.confirm(confirmation)) return;
    const output = $('#sandbox-result'); output.textContent = networkAccess
      ? 'Preparing sanitized workspace and starting a container with approved, unrestricted bridge networking…'
      : 'Preparing sanitized workspace and starting an isolated offline container…';
    $('#sandbox-propose-ui').hidden = true;
    lastSandboxRunId = null; lastSandboxProposablePaths = [];
    $('#sandbox-run-button').disabled = true;
    try {
      const result = await api('/api/sandbox/run', { method: 'POST', body: JSON.stringify({ command, cwd: '.', timeout_seconds: 30, network_access: networkAccess }) });
      output.textContent = JSON.stringify(result, null, 2);
      renderSandboxProposalChoices(result);
      if (result.proposable_files?.length) toast(`${result.proposable_files.length} changed text file(s) can be sent to the Approval Queue as proposals.`);
    } catch (error) { output.textContent = `Sandbox run failed: ${error.message}`; }
    finally {
      $('#sandbox-network-access').checked = false; // Every run must opt into broad egress again.
      $('#sandbox-run-button').disabled = !(extensionData?.sandbox?.ready);
    }
  });

  $('#sandbox-propose-button').addEventListener('click', async () => {
    const paths = $$('[data-sandbox-path]:checked').map((element) => element.dataset.sandboxPath).filter(Boolean);
    if (!lastSandboxRunId || !paths.length) { toast('Select at least one eligible file change.'); return; }
    const button = $('#sandbox-propose-button'); button.disabled = true;
    try {
      const result = await api('/api/sandbox/propose-changes', { method: 'POST', body: JSON.stringify({ sandbox_run_id: lastSandboxRunId, paths }) });
      const submitted = new Set(paths);
      lastSandboxProposablePaths = lastSandboxProposablePaths.filter((path) => !submitted.has(path));
      $$('[data-sandbox-path]').forEach((input) => { if (submitted.has(input.dataset.sandboxPath)) { input.checked = false; input.disabled = true; input.closest('.sandbox-propose-row')?.classList.add('submitted'); } });
      $('#sandbox-result').textContent += `\n\n${result.message}\nCreated proposals: ${(result.proposals || []).map((row) => row.path).join(', ') || 'none'}${result.failures?.length ? `\nSkipped: ${JSON.stringify(result.failures)}` : ''}`;
      await loadActions();
      toast(`Created ${result.proposals?.length || 0} reviewable proposal(s); no files were changed.`);
      showPanel('approvals');
    } catch (error) { toast(`Could not create proposals: ${error.message}`); }
    finally { button.disabled = false; }
  });

  refreshStatus();
  loadActions();
  loadMetrics();
  loadPermissions().catch(() => {});
  initializeConversations();
  loadExtensions().catch(() => {});

  // Knowledge Studio uses request epochs so a slower, older query cannot overwrite newer results.
  function formatRagBytes(bytes) {
    const value = Number(bytes || 0);
    return value < 1024 ? `${value} B` : value < 1024 * 1024 ? `${(value / 1024).toFixed(1)} KB` : `${(value / 1024 / 1024).toFixed(2)} MB`;
  }
  function setRagUploadStatus(message, kind = '') {
    const node = $('#rag-upload-status');
    if (!node) return;
    node.textContent = message;
    node.classList.toggle('good', kind === 'good');
    node.classList.toggle('bad', kind === 'bad');
  }
  function renderRagStatus(status) {
    if (!status) return;
    $('#rag-stat-docs').textContent = Number(status.documents || 0).toLocaleString();
    $('#rag-stat-chunks').textContent = Number(status.chunks || 0).toLocaleString();
    $('#rag-stat-mode').textContent = status.fts_available ? (status.semantic_search_active ? 'Hybrid' : 'Lexical') : 'Fallback';
    $('#rag-stat-embed').textContent = status.semantic_search_active ? 'Active' : status.semantic_search_configured ? 'Configured' : 'Off';
    $('#rag-nav-count').textContent = Number(status.documents || 0) > 99 ? '99+' : String(status.documents || 0);
    const pill = $('#rag-status-pill');
    pill.textContent = status.documents ? `${status.documents} documents · ${status.chunks} chunks` : 'Library ready · empty';
    pill.classList.toggle('on', Number(status.documents || 0) > 0);
    $('#rag-engine-detail').textContent = `Storage: ${status.storage || 'local SQLite'} · lexical: ${status.fts_available ? 'FTS5 ready' : 'token-overlap fallback'} · semantic: ${status.semantic_search_active ? `active (${status.embedding_model || 'configured model'})` : status.semantic_search_configured ? 'configured; index documents to build vectors' : 'optional, currently off'}. ${status.privacy_note || 'Review the configured embedding boundary before indexing private material.'}`;
    const searchPrivacy = $('#rag-search-note');
    if (searchPrivacy) searchPrivacy.textContent = status.embedding_requests_include_chunk_text ? `Chunk text is sent to ${status.embedding_endpoint_host || 'the configured embedding endpoint'} for vectors; documents remain stored locally.` : 'No embedding provider configured: retrieval uses the local lexical index and does not send chunks for embeddings.';
  }
  function renderRagDocuments(rows) {
    const host = $('#rag-documents');
    host.replaceChildren();
    const allRows = Array.isArray(rows) ? rows : [];
    const filter = String($('#rag-library-filter')?.value || '').trim().toLowerCase();
    const sourceFilter = $('#rag-library-source')?.value || 'all';
    const filtered = allRows.filter((row) => {
      const isWorkspace = String(row.source || '').startsWith('workspace:') || row.source === 'workspace';
      const matchesSource = sourceFilter === 'all' || (sourceFilter === 'workspace' ? isWorkspace : !isWorkspace);
      const haystack = `${row.filename || ''} ${row.source || ''}`.toLowerCase();
      return matchesSource && (!filter || haystack.includes(filter));
    });
    const count = $('#rag-library-count');
    if (count) count.textContent = filtered.length === allRows.length ? `${allRows.length} docs` : `${filtered.length} / ${allRows.length}`;
    if (!allRows.length) {
      const empty = document.createElement('div'); empty.className = 'empty';
      empty.textContent = 'No documents yet. Add notes or code, or index your selected workspace. PDF parsing is disabled by default for security.';
      host.append(empty); return;
    }
    if (!filtered.length) {
      const empty = document.createElement('div'); empty.className = 'empty';
      empty.textContent = 'No documents match these filters. Clear the filename filter or choose “All sources”.';
      host.append(empty); return;
    }
    filtered.forEach((row) => {
      const item = document.createElement('article'); item.className = 'rag-doc-row';
      const icon = document.createElement('span'); icon.className = 'rag-doc-icon'; icon.textContent = (String(row.filename || '').split('.').pop() || 'DOC').slice(0, 4).toUpperCase();
      const main = document.createElement('div'); main.className = 'rag-doc-main';
      const title = document.createElement('b'); title.textContent = row.filename || 'Unnamed document'; title.title = row.filename || '';
      const meta = document.createElement('small'); meta.textContent = `${Number(row.chunk_count || 0)} chunks · ${formatRagBytes(row.size_bytes)} · ${row.embedding_indexed ? 'semantic + lexical' : 'lexical'}`;
      main.append(title, meta);
      const controls = document.createElement('div'); controls.className = 'rag-doc-controls';
      const source = document.createElement('span'); source.className = 'rag-source-tag'; source.textContent = row.source?.startsWith('workspace:') ? 'WORKSPACE' : row.source === 'workspace' ? 'WORKSPACE' : 'UPLOAD';
      const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'rag-delete'; remove.textContent = 'Remove'; remove.setAttribute('aria-label', `Remove ${row.filename} from the local index`);
      remove.addEventListener('click', async () => {
        if (!window.confirm(`Remove “${row.filename}” from Origo's local index? The original file will not be changed.`)) return;
        remove.disabled = true;
        try {
          await api(`/api/rag/documents/${encodeURIComponent(row.doc_id)}`, { method: 'DELETE' });
          uiState.dispatch({ type: 'KNOWLEDGE_PATCH', patch: { results: null } });
          $('#rag-results').replaceChildren(); $('#rag-ask-copilot').disabled = true;
          $('#rag-results-summary').textContent = 'A source was removed from the library. Search again to refresh evidence against the updated index.';
          toast(`Removed ${row.filename} from the library.`); await loadRagStudio();
        }
        catch (error) { toast(`Could not remove document: ${error.message}`); remove.disabled = false; }
      });
      controls.append(source, remove); item.append(icon, main, controls); host.append(item);
    });
  }
  async function loadRagStudio() {
    const token = uiState.beginRequest('ragLoad');
    uiState.dispatch({ type: 'KNOWLEDGE_PATCH', patch: { loading: true } });
    try {
      const [status, documents] = await Promise.all([api('/api/rag/status'), api('/api/rag/documents?limit=200')]);
      if (!uiState.requestIsCurrent('ragLoad', token)) return;
      uiState.dispatch({ type: 'KNOWLEDGE_PATCH', patch: { status, documents: documents.documents || [], loading: false } });
      renderRagStatus(status); renderRagDocuments(documents.documents || []);
    } catch (error) {
      if (!uiState.requestIsCurrent('ragLoad', token)) return;
      uiState.dispatch({ type: 'KNOWLEDGE_PATCH', patch: { loading: false } });
      $('#rag-status-pill').textContent = 'Library unavailable';
      $('#rag-engine-detail').textContent = `The local RAG API could not be reached: ${error.message}`;
    }
  }
  function renderRagResults(result) {
    const host = $('#rag-results'); host.replaceChildren();
    const rows = result?.results || [];
    $('#rag-results-summary').textContent = rows.length
      ? `${rows.length} source passage${rows.length === 1 ? '' : 's'} · ${result.confidence || 'unrated'} confidence · ${result.retrieval_mode || 'lexical'} retrieval. Treat low-confidence matches as leads, not answers.`
      : 'No matching evidence. Add documents or try more distinctive terms.';
    const ragPrivacy = uiState.get().knowledge.status?.privacy_note || 'Document storage is local. Review embedding endpoint settings before enabling semantic retrieval.';
    $('#rag-search-note').textContent = result?.embedding_error ? `Embedding route unavailable (${result.embedding_error}); lexical retrieval continued. ${ragPrivacy}` : `Rank fusion: ${result?.fusion || 'BM25 + optional semantic retrieval'}. ${ragPrivacy}`;
    const queryStillMatches = String($('#rag-query').value || '').trim() === String(result?.query || uiState.get().knowledge.query || '').trim();
    $('#rag-ask-copilot').disabled = !rows.length || !queryStillMatches;
    if (!rows.length) {
      const empty = document.createElement('div'); empty.className = 'empty'; empty.textContent = 'Nothing retrieved for this query. Search does not generate an answer when evidence is missing.'; host.append(empty); return;
    }
    rows.forEach((row, index) => {
      const card = document.createElement('article'); card.className = 'rag-result';
      const head = document.createElement('div'); head.className = 'rag-result-head';
      const ref = document.createElement('span'); ref.className = 'rag-citation'; ref.textContent = `[${row.citation_id || `R${index + 1}`}]`;
      const name = document.createElement('div'); name.className = 'rag-result-name';
      const file = document.createElement('b'); file.textContent = row.filename || 'Unknown source';
      const loc = document.createElement('small'); loc.textContent = `Chunk ${Number(row.chunk_index || 0) + 1}${row.page ? ` · Page ${row.page}` : ''} · ${row.source?.startsWith('workspace:') ? row.source.slice(10) : row.source || 'local upload'}`;
      name.append(file, loc);
      const score = document.createElement('span'); score.className = 'rag-score'; score.textContent = `${Math.round(Number(row.score || 0) * 100)}% signal`;
      head.append(ref, name, score);
      const passage = document.createElement('pre'); passage.className = 'rag-passage'; passage.textContent = row.text || '';
      const foot = document.createElement('div'); foot.className = 'rag-result-foot';
      const evidence = document.createElement('small'); evidence.textContent = `${Math.round(Number(row.term_coverage || 0) * 100)}% query-term coverage${row.phrase_match ? ' · exact phrase' : ''}${row.semantic_rank ? ` · semantic rank ${row.semantic_rank}` : ''}`;
      const copy = document.createElement('button'); copy.type = 'button'; copy.className = 'rag-copy-cite'; copy.textContent = `Copy [${row.citation_id}]`;
      copy.addEventListener('click', async () => {
        const text = `[${row.citation_id}] ${row.filename} · chunk ${Number(row.chunk_index || 0) + 1}`;
        try { await navigator.clipboard.writeText(text); toast('Citation copied.'); }
        catch { toast(text); }
      });
      foot.append(evidence, copy); card.append(head, passage, foot); host.append(card);
    });
  }
  async function searchRag(event) {
    event?.preventDefault();
    const query = $('#rag-query').value.trim();
    if (!query) { toast('Enter a question or search phrase first.'); return; }
    const limit = Math.max(1, Math.min(12, Number($('#rag-limit').value) || 8));
    const token = uiState.beginRequest('ragSearch');
    uiState.dispatch({ type: 'KNOWLEDGE_PATCH', patch: { query, limit, loading: true, results: null } });
    $('#rag-search-button').disabled = true; $('#rag-search-button').textContent = 'Retrieving…';
    $('#rag-ask-copilot').disabled = true; $('#rag-results').replaceChildren();
    $('#rag-results-summary').textContent = 'Searching the local index and reranking candidate passages…';
    try {
      const result = await api('/api/rag/search', { method: 'POST', body: JSON.stringify({ query, limit, include_context: true }) });
      if (!uiState.requestIsCurrent('ragSearch', token)) return;
      if ($('#rag-query').value.trim() !== query) {
        uiState.dispatch({ type: 'KNOWLEDGE_PATCH', patch: { results: null, loading: false } });
        $('#rag-results-summary').textContent = 'The query changed while retrieval was running. Run the search again so evidence matches the current question.';
        $('#rag-results').replaceChildren(); $('#rag-ask-copilot').disabled = true;
        return;
      }
      uiState.dispatch({ type: 'KNOWLEDGE_PATCH', patch: { results: result, loading: false } });
      renderRagResults(result);
    } catch (error) {
      if (!uiState.requestIsCurrent('ragSearch', token)) return;
      uiState.dispatch({ type: 'KNOWLEDGE_PATCH', patch: { loading: false, results: null } });
      $('#rag-results-summary').textContent = `Search failed: ${error.message}`;
      $('#rag-results').replaceChildren(); $('#rag-ask-copilot').disabled = true;
    } finally {
      if (uiState.requestIsCurrent('ragSearch', token)) { $('#rag-search-button').disabled = false; $('#rag-search-button').textContent = 'Search library ↗'; }
    }
  }
  async function ingestRagFiles(files) {
    const selected = [...(files || [])];
    if (!selected.length) return;
    if (selected.length > 8) { toast('Index up to 8 files per batch to keep memory and failure recovery bounded.'); return; }
    const resultBox = $('#rag-ingest-results'); resultBox.hidden = false; resultBox.replaceChildren();
    let successes = 0;
    $('#rag-choose-files').disabled = true; $('#rag-index-workspace').disabled = true;
    try {
      for (const file of selected) {
        if (!file.size || file.size > 7 * 1024 * 1024) {
          const row = document.createElement('div'); row.className = 'rag-ingest-row bad'; row.textContent = `${file.name}: must be between 1 byte and 7 MiB.`; resultBox.append(row); continue;
        }
        setRagUploadStatus(`Indexing ${file.name} (${formatRagBytes(file.size)})…`);
        try {
          const encoded = await fileAsBase64(file);
          const result = await api('/api/rag/ingest', { method: 'POST', body: JSON.stringify({ filename: file.name, mime_type: file.type || 'application/octet-stream', content_base64: encoded }) });
          const row = document.createElement('div'); row.className = 'rag-ingest-row good';
          row.textContent = `✓ ${result.filename} · ${result.chunk_count} chunks${result.secrets_redacted ? ` · redacted ${result.secrets_redacted} credential-like value(s)` : ''}${result.embedding_indexed ? ' · semantic vectors saved' : ' · lexical index ready'}`;
          resultBox.append(row); successes++;
        } catch (error) {
          const row = document.createElement('div'); row.className = 'rag-ingest-row bad'; row.textContent = `× ${file.name}: ${error.message}`; resultBox.append(row);
        }
      }
      setRagUploadStatus(`${successes} of ${selected.length} file(s) indexed.`, successes ? 'good' : 'bad');
      await loadRagStudio();
      if (successes) toast(`Knowledge index updated: ${successes} file(s).`);
    } finally {
      $('#rag-choose-files').disabled = false; $('#rag-index-workspace').disabled = false; $('#rag-file-input').value = '';
    }
  }
  async function indexRagWorkspace() {
    const button = $('#rag-index-workspace');
    if (!window.confirm('Index up to 60 readable, non-sensitive text/code files from the selected workspace? This reads files into Origo’s local knowledge database; it does not modify source files.')) return;
    button.disabled = true; setRagUploadStatus('Scanning selected workspace with secret and size filters…');
    const box = $('#rag-ingest-results'); box.hidden = false; box.textContent = 'Workspace indexing started…';
    try {
      const report = await api('/api/rag/index-workspace', { method: 'POST', body: JSON.stringify({}) });
      const indexed = report.indexed || [];
      box.replaceChildren();
      const summary = document.createElement('div'); summary.className = 'rag-ingest-row good';
      summary.textContent = `Indexed ${indexed.length} file(s), ${indexed.reduce((sum, row) => sum + Number(row.chunk_count || 0), 0)} chunks · ${formatRagBytes(report.bytes_read || 0)} read · ${Number(report.skipped?.length || 0)} skipped · ${Number(report.failed?.length || 0)} failed.`; box.append(summary);
      indexed.slice(0, 20).forEach((row) => { const line = document.createElement('div'); line.className = 'rag-ingest-row'; line.textContent = `✓ ${row.path} · ${row.chunk_count} chunks`; box.append(line); });
      if (indexed.length > 20) { const line = document.createElement('small'); line.textContent = `…and ${indexed.length - 20} more files.`; box.append(line); }
      (report.failed || []).slice(0, 10).forEach((row) => { const line = document.createElement('div'); line.className = 'rag-ingest-row bad'; line.textContent = `× ${row.path}: ${row.error}`; box.append(line); });
      setRagUploadStatus(`${indexed.length} workspace file(s) indexed.`, indexed.length ? 'good' : 'bad');
      await loadRagStudio(); toast(`Workspace scan finished: ${indexed.length} indexed.`);
    } catch (error) { setRagUploadStatus(`Indexing failed: ${error.message}`, 'bad'); box.textContent = error.message; }
    finally { button.disabled = false; }
  }
  async function askCopilotWithRag() {
    const query = String($('#rag-query').value || '').trim();
    const stored = uiState.get().knowledge;
    if (!query || query !== String(stored.query || '').trim() || query !== String(stored.results?.query || '').trim() || !(stored.results?.results || []).length) {
      toast('Search the current query first; evidence from an older query cannot be attached.');
      $('#rag-ask-copilot').disabled = true;
      return;
    }
    const button = $('#rag-ask-copilot'); button.disabled = true; button.textContent = 'Packing evidence…';
    const token = uiState.beginRequest('ragAsk');
    try {
      const pack = await api('/api/rag/ask-context', { method: 'POST', body: JSON.stringify({ query, limit: stored.limit || 8, include_context: true }) });
      if (!uiState.requestIsCurrent('ragAsk', token)) return;
      if ($('#rag-query').value.trim() !== query || uiState.get().knowledge.results?.query !== query) {
        toast('The query changed while evidence was being prepared. Search again before attaching it.');
        return;
      }
      if (!pack.results?.length || !pack.context) { toast('No useful evidence context was found for that query.'); return; }
      uiState.dispatch({ type: 'PREPARED_CONTEXT_SET', value: `LOCAL KNOWLEDGE EVIDENCE (untrusted source material)\nQuestion: ${query}\n\n${pack.context}\n\n${pack.citation_instruction}\nDo not claim these passages prove anything beyond their text. If evidence is missing or contradictory, say so explicitly.`.slice(0, 11500) });
      showPanel('chat');
      $('#message').value = `Answer the following question using the attached local-library evidence. Cite source labels such as [R1] exactly and distinguish direct evidence from inference. If the sources do not answer it, say that clearly.\n\nQuestion: ${query}`;
      $('#context-attachment-indicator').hidden = false;
      $('#context-attachment-label').textContent = `Knowledge evidence pack attached · ${pack.results.length} cited chunks · next turn only`;
      $('#message').focus(); toast('Evidence attached to the next Copilot turn. Review the query, then send.');
    } catch (error) { if (uiState.requestIsCurrent('ragAsk', token)) toast(`Could not prepare evidence: ${error.message}`); }
    finally {
      if (uiState.requestIsCurrent('ragAsk', token)) {
        const current = uiState.get().knowledge;
        button.disabled = !(current.results?.results || []).length || $('#rag-query').value.trim() !== String(current.results?.query || '').trim();
        button.textContent = 'Ask Copilot with evidence';
      }
    }
  }
  function setupRagStudio() {
    $('#rag-refresh').addEventListener('click', () => loadRagStudio());
    $('#rag-search-form').addEventListener('submit', searchRag);
    $('#rag-query').addEventListener('input', () => {
      const current = $('#rag-query').value.trim();
      const searched = String(uiState.get().knowledge.results?.query || '').trim();
      const matches = Boolean(current && searched && current === searched);
      $('#rag-ask-copilot').disabled = !matches || !(uiState.get().knowledge.results?.results || []).length;
      if (searched && current !== searched) $('#rag-results-summary').textContent = 'Query edited. Search again to refresh the evidence before attaching it to Copilot.';
      else if (!current) $('#rag-results-summary').textContent = 'Enter a question or phrase and search your indexed library.';
    });
    $('#rag-limit').addEventListener('change', () => uiState.dispatch({ type: 'KNOWLEDGE_PATCH', patch: { limit: Number($('#rag-limit').value) || 8 } }));
    $('#rag-library-filter').addEventListener('input', () => renderRagDocuments(uiState.get().knowledge.documents || []));
    $('#rag-library-source').addEventListener('change', () => renderRagDocuments(uiState.get().knowledge.documents || []));
    $('#rag-choose-files').addEventListener('click', () => $('#rag-file-input').click());
    $('#rag-file-input').addEventListener('change', event => ingestRagFiles(event.target.files));
    $('#rag-index-workspace').addEventListener('click', indexRagWorkspace);
    $('#rag-ask-copilot').addEventListener('click', askCopilotWithRag);
    const dropzone = $('#rag-dropzone');
    ['dragenter','dragover'].forEach(type => dropzone.addEventListener(type, event => { event.preventDefault(); dropzone.classList.add('drag-over'); }));
    ['dragleave','drop'].forEach(type => dropzone.addEventListener(type, event => { event.preventDefault(); dropzone.classList.remove('drag-over'); }));
    dropzone.addEventListener('drop', event => ingestRagFiles(event.dataTransfer?.files));
  }
  setupRagStudio();

  // Keyboard-first command palette. Actions run only after an explicit selection.
  const commandPalette = $('#command-palette');
  const commandSearch = $('#command-palette-search');
  const commandList = $('#command-palette-list');
  let commandPaletteOpener = null;
  let selectedCommandIndex = 0;
  const commandItems = [
    {id:'new-chat',label:'New conversation',description:'Start a fresh thread',icon:'＋',keywords:'chat conversation new',shortcut:'',run:()=>createConversation({render:true}).catch(error=>toast(error.message))},
    {id:'focus-composer',label:'Focus message composer',description:'Return to the chat input',icon:'✎',keywords:'write message prompt chat',shortcut:'',run:()=>{showPanel('chat');$('#message').focus();}},
    {id:'chat',label:'Open Copilot',description:'Return to your assistant workspace',icon:'◈',keywords:'chat home copilot',shortcut:'',run:()=>showPanel('chat')},
    {id:'files',label:'Open Files & context',description:'Workspace, scratchpad, and project files',icon:'▤',keywords:'files context scratchpad project',shortcut:'',run:()=>showPanel('files')},
    {id:'knowledge',label:'Open Knowledge Studio',description:'Index local documents and inspect cited retrieval evidence',icon:'⌕',keywords:'knowledge rag retrieval documents library citations search embeddings',shortcut:'',run:()=>showPanel('knowledge')},
    {id:'scratchpad',label:'Quick-capture project note',description:'Open your explicit, inspectable scratchpad',icon:'▧',keywords:'note capture hypothesis memory',shortcut:'',run:()=>{showPanel('files');window.setTimeout(()=>$('#scratchpad-content')?.focus(),0);}},
    {id:'approvals',label:'Review approval queue',description:'Inspect proposed actions and changes',icon:'✓',keywords:'approval review permission action',shortcut:'',run:()=>showPanel('approvals')},
    {id:'runs',label:'Open run history',description:'Review prior agent runs and metrics',icon:'◷',keywords:'history runs logs metrics',shortcut:'',run:()=>showPanel('runs')},
    {id:'extensions',label:'Open skills & plugins',description:'Inspect locally available capabilities',icon:'⊞',keywords:'skills plugins tools extensions',shortcut:'',run:()=>showPanel('extensions')},
    {id:'permissions',label:'Open permission center',description:'Review network and sandbox policy',icon:'◇',keywords:'security privacy policy permissions',shortcut:'',run:()=>showPanel('permissions')},
    {id:'diagnostics',label:'Open diagnostics',description:'Inspect providers and local services',icon:'⌁',keywords:'health status provider model diagnostics',shortcut:'',run:()=>showPanel('diagnostics')},
    {id:'scout',label:'Run read-only self-test',description:'Check application contracts without inference',icon:'✓',keywords:'scout test checks verify',shortcut:'',run:()=>{showPanel('diagnostics');runScout();}},
    {id:'hmi-audit',label:'Review interface quality',description:'Run HMI/accessibility static heuristics',icon:'◎',keywords:'hmi usability psychology accessibility audit',shortcut:'',run:()=>{showPanel('diagnostics');runHmiAudit();}},
    {id:'capsule',label:'Create signed research Capsule',description:'Package selected artifacts and verify integrity',icon:'◇',keywords:'capsule reproducibility signature research archive',shortcut:'',run:()=>{showPanel('diagnostics');window.setTimeout(()=>$('#capsule-paths')?.focus(),0);}},
    {id:'proof-ledger',label:'Review Proof Ledger',description:'Attach exact evidence and lint research claims',icon:'▤',keywords:'proof ledger evidence claim citations result',shortcut:'',run:()=>{showPanel('diagnostics');window.setTimeout(()=>$('#proof-evidence-path')?.focus(),0);}},
    {id:'focus-mode',label:'Toggle focus mode',description:'Hide navigation chrome for a quieter workspace',icon:'◌',keywords:'focus distraction minimal view',shortcut:'',run:()=>toggleFocusMode()},
    {id:'theme',label:'Switch light or dark theme',description:'Change the workstation appearance',icon:'◐',keywords:'light dark theme appearance color',shortcut:'',run:()=>setTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light')}
  ];
  function toggleFocusMode(force) {
    const on = typeof force === 'boolean' ? force : !document.body.classList.contains('focus-mode');
    document.body.classList.toggle('focus-mode', on);
    uiState.dispatch({ type: 'FOCUS_SET', value: on });
    toast(on ? 'Focus mode enabled. Press Ctrl/Command+K to leave.' : 'Focus mode disabled.');
  }
  if (uiState.get().focusMode) document.body.classList.add('focus-mode');
  function getFilteredCommands() {
    const q = String(commandSearch?.value || '').trim().toLowerCase();
    return commandItems.filter((item) => !q || `${item.label} ${item.description} ${item.keywords}`.toLowerCase().includes(q));
  }
  function renderCommandPalette() {
    if (!commandList) return;
    const filtered = getFilteredCommands();
    selectedCommandIndex = Math.max(0, Math.min(selectedCommandIndex, filtered.length - 1));
    commandList.replaceChildren();
    if (!filtered.length) {
      const empty = document.createElement('div'); empty.className = 'command-empty'; empty.textContent = 'No matching commands. Try “knowledge”, “files”, “audit”, or “focus”.'; commandList.append(empty); return;
    }
    filtered.forEach((item, index) => {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'command-option';
      button.setAttribute('role', 'option'); button.setAttribute('aria-selected', String(index === selectedCommandIndex));
      const icon = document.createElement('span'); icon.className = 'command-icon'; icon.textContent = item.icon;
      const detail = document.createElement('span'); const title = document.createElement('b'); title.textContent = item.label;
      const desc = document.createElement('small'); desc.textContent = item.description; detail.append(title, desc);
      const shortcut = document.createElement('kbd'); shortcut.textContent = item.shortcut;
      button.append(icon, detail, shortcut); button.addEventListener('mouseenter', () => { selectedCommandIndex = index; [...commandList.querySelectorAll('[role=\"option\"]')].forEach((option, optionIndex) => option.setAttribute('aria-selected', String(optionIndex === index))); });
      button.addEventListener('click', () => { closeCommandPalette(); try { item.run(); } catch (error) { toast(`Command failed: ${error.message}`); } });
      commandList.append(button);
    });
    const options = [...commandList.querySelectorAll('[role="option"]')]; options[selectedCommandIndex]?.setAttribute('aria-selected', 'true');
  }
  function openCommandPalette() {
    if (!commandPalette) return;
    commandPaletteOpener = document.activeElement;
    commandPalette.hidden = false; document.body.classList.add('modal-open'); selectedCommandIndex = 0;
    if (commandSearch) commandSearch.value = '';
    renderCommandPalette(); commandSearch?.focus({preventScroll:true});
  }
  function closeCommandPalette() {
    if (!commandPalette || commandPalette.hidden) return;
    commandPalette.hidden = true; document.body.classList.remove('modal-open');
    if (commandPaletteOpener && typeof commandPaletteOpener.focus === 'function') commandPaletteOpener.focus({preventScroll:true});
  }
  $('#command-palette-open')?.addEventListener('click', openCommandPalette);
  commandPalette?.addEventListener('click', (event) => { if (event.target?.dataset?.commandClose === 'true') closeCommandPalette(); });
  commandSearch?.addEventListener('input', () => { selectedCommandIndex = 0; renderCommandPalette(); });
  commandPalette?.addEventListener('keydown', (event) => {
    const options = [...(commandList?.querySelectorAll('[role="option"]') || [])];
    if (event.key === 'Escape') { event.preventDefault(); closeCommandPalette(); return; }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault(); if (!options.length) return;
      selectedCommandIndex = (selectedCommandIndex + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length;
      options.forEach((option,index)=>option.setAttribute('aria-selected', String(index === selectedCommandIndex)));
      options[selectedCommandIndex]?.focus(); return;
    }
    if (event.key === 'Enter' && document.activeElement === commandSearch && options.length) { event.preventDefault(); options[selectedCommandIndex]?.click(); return; }
    if (event.key === 'Tab') {
      const focusables = [commandSearch, ...options].filter((node)=>node && !node.disabled);
      if (!focusables.length) { event.preventDefault(); return; }
      const current = focusables.indexOf(document.activeElement);
      const next = event.shiftKey
        ? (current <= 0 ? focusables.length - 1 : current - 1)
        : (current < 0 || current === focusables.length - 1 ? 0 : current + 1);
      event.preventDefault(); focusables[next].focus();
    }
  });

  // Ori is intentionally a lightweight, opt-outable companion, not an OS agent.
  const ori = $('#ori-companion');
  const oriBubble = $('#ori-bubble');
  let oriSeconds = (() => { try { return Math.max(0, Math.min(24 * 3600, Number(localStorage.getItem('indra.ori.activeSeconds') || 0))); } catch { return 0; } })();
  let oriSnoozeUntil = 0;
  let oriNudgeShown = false;
  let oriEnabled = (() => { try { return localStorage.getItem('indra.ori.reminders') !== 'off'; } catch { return true; } })();
  const oriReminders = $('#ori-reminders');
  if (oriReminders) oriReminders.checked = oriEnabled;
  function setOriBubble(open, title, message, nudge = false) {
    if (!oriBubble || !ori) return;
    oriBubble.hidden = !open;
    $('#ori-open').setAttribute('aria-expanded', String(open));
    if (title) $('#ori-bubble-title').textContent = title;
    if (message) $('#ori-bubble-text').textContent = message;
    ori.classList.toggle('nudge', nudge);
    if (open) $('#ori-close').focus({ preventScroll: true });
  }
  $('#ori-open')?.addEventListener('click', () => {
    const opening = oriBubble.hidden;
    setOriBubble(opening, 'Hey, I’m Ori ✨', 'I’m your little workspace companion. Ask for a thinking partner, a tiny reset, or help figuring out your next step.');
  });
  $('#ori-close')?.addEventListener('click', () => {
    if ($('#ori-later').textContent === 'I’m back') { $('#ori-talk').hidden = false; $('#ori-break').hidden = false; $('#ori-later').textContent = 'Later'; }
    setOriBubble(false);
  });
  oriReminders?.addEventListener('change', () => {
    oriEnabled = oriReminders.checked;
    try { localStorage.setItem('indra.ori.reminders', oriEnabled ? 'on' : 'off'); } catch { /* Session-only preference is fine. */ }
    if (!oriEnabled) { oriNudgeShown = false; setOriBubble(false); toast('Break nudges paused. Ori is still here when you need them.'); }
    else { oriSeconds = 0; oriSnoozeUntil = 0; toast('Gentle break nudges enabled for every 50 minutes this tab is active.'); }
  });
  $('#ori-talk')?.addEventListener('click', () => {
    showPanel('chat');
    const input = $('#message');
    input.value = 'Hey Ori, be a friendly thinking companion for a moment. Ask me one gentle question about what is on my mind, then help me choose a useful next step. Do not assume what I feel.';
    input.focus(); input.scrollIntoView({ block: 'center', behavior: 'smooth' });
    setOriBubble(false);
  });
  $('#ori-break')?.addEventListener('click', () => {
    oriSeconds = 0; oriNudgeShown = false; oriSnoozeUntil = 0;
    try { localStorage.setItem('indra.ori.activeSeconds', '0'); } catch { /* Current tab continues. */ }
    setOriBubble(true, 'Good call. 🌿', 'Step away from the screen, stretch your shoulders, look at something far away, and get a sip of water. I’ll be here when you’re back.');
    $('#ori-talk').hidden = true; $('#ori-break').hidden = true; $('#ori-later').textContent = 'I’m back';
  });
  $('#ori-later')?.addEventListener('click', () => {
    if ($('#ori-later').textContent === 'I’m back') {
      $('#ori-talk').hidden = false; $('#ori-break').hidden = false; $('#ori-later').textContent = 'Later';
      setOriBubble(false); toast('Welcome back. Your active-time counter has reset.'); return;
    }
    oriSnoozeUntil = Date.now() + 10 * 60 * 1000; oriNudgeShown = false;
    setOriBubble(false); toast('Ori will gently remind you again in 10 minutes.');
  });
  window.setInterval(() => {
    if (!oriEnabled || document.visibilityState !== 'visible') return;
    oriSeconds += 1;
    if (oriSeconds % 30 === 0) { try { localStorage.setItem('indra.ori.activeSeconds', String(oriSeconds)); } catch { /* Keep the counter in memory. */ } }
    if (oriSeconds >= 50 * 60 && !oriNudgeShown && Date.now() >= oriSnoozeUntil) {
      oriNudgeShown = true;
      setOriBubble(true, 'A tiny reset?', 'You have had about 50 active minutes in Origo. Want to stretch, hydrate, or just talk through what is on your mind?', true);
    }
  }, 1000);
})();
