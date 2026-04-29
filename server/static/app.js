const welcomeMessage = {
  role: "assistant",
  content: "你好，我是知识库问答助手。请选择左侧历史会话，或点击新对话开始提问。",
};

const state = {
  conversations: [],
  currentConversationId: null,
  messages: [welcomeMessage],
  trace: ["[system] 页面已加载"],
  lastResult: null,
};

const els = {
  conversationList: document.querySelector("#conversationList"),
  newConversation: document.querySelector("#newConversationButton"),
  currentTitle: document.querySelector("#currentConversationTitle"),
  chatList: document.querySelector("#chatList"),
  form: document.querySelector("#chatForm"),
  input: document.querySelector("#messageInput"),
  send: document.querySelector("#sendButton"),
  health: document.querySelector("#healthBadge"),
  fileCount: document.querySelector("#fileCount"),
  docCount: document.querySelector("#docCount"),
  vectorState: document.querySelector("#vectorState"),
  lastRebuild: document.querySelector("#lastRebuild"),
  traceLog: document.querySelector("#traceLog"),
  refresh: document.querySelector("#refreshButton"),
  rebuild: document.querySelector("#rebuildButton"),
  fileInput: document.querySelector("#fileInput"),
  fileList: document.querySelector("#fileList"),
  kbMessage: document.querySelector("#kbMessage"),
  copyTrace: document.querySelector("#copyTraceButton"),
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function nowTime() {
  return new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

function pushTrace(line) {
  state.trace.unshift(`[${nowTime()}] ${line}`);
  state.trace = state.trace.slice(0, 10);
  renderTrace();
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function apiJson(url, options = {}) {
  const headers = options.body instanceof FormData
    ? { ...(options.headers || {}) }
    : { "Content-Type": "application/json", ...(options.headers || {}) };
  const response = await fetch(url, { ...options, headers });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(data.detail || data.error || `HTTP ${response.status}`);
  }
  return data;
}

function renderMessages() {
  els.currentTitle.textContent = currentConversationTitle();
  els.chatList.innerHTML = state.messages
    .map((item) => {
      const roleName = item.role === "user" ? "你" : "系统";
      return `
        <div class="message-row ${item.role}">
          <div class="message-meta">${roleName}</div>
          <div class="message-bubble">${escapeHtml(item.content || "")}</div>
        </div>
      `;
    })
    .join("");
  els.chatList.scrollTop = els.chatList.scrollHeight;
}

function renderConversations() {
  els.conversationList.innerHTML = state.conversations.length
    ? state.conversations
        .map((item) => {
          const active = item.id === state.currentConversationId ? " active" : "";
          return `
            <div class="conversation-item${active}" data-conversation-id="${escapeHtml(item.id)}">
              <button class="conversation-open" type="button" title="${escapeHtml(item.title)}">
                <strong>${escapeHtml(item.title)}</strong>
                <span>${escapeHtml(item.updated_at)}</span>
              </button>
              <button class="conversation-delete" type="button" data-delete-conversation="${escapeHtml(item.id)}">删除</button>
            </div>
          `;
        })
        .join("")
    : `<div class="empty">暂无历史会话</div>`;
}

function renderTrace() {
  els.traceLog.textContent = state.trace.join("\n");
}

function currentConversationTitle() {
  const current = state.conversations.find((item) => item.id === state.currentConversationId);
  return current ? current.title : "新对话";
}

function setBusy(busy) {
  els.send.disabled = busy;
  els.input.disabled = busy;
  els.newConversation.disabled = busy;
  els.send.textContent = busy ? "处理中" : "发送";
}

async function loadConversations() {
  const data = await apiJson("/api/conversations");
  state.conversations = data.conversations;
  renderConversations();
}

async function createConversation(openImmediately = true) {
  const data = await apiJson("/api/conversations", { method: "POST" });
  await loadConversations();
  if (openImmediately) {
    await loadConversation(data.conversation.id);
  }
  pushTrace("已创建新对话");
  return data.conversation.id;
}

async function loadConversation(conversationId) {
  const data = await apiJson(`/api/conversations/${encodeURIComponent(conversationId)}`);
  state.currentConversationId = data.conversation.id;
  state.messages = data.messages.length ? data.messages : [welcomeMessage];
  renderConversations();
  renderMessages();
  pushTrace(`已切换会话：${data.conversation.title}`);
}

async function deleteConversation(conversationId) {
  await apiJson(`/api/conversations/${encodeURIComponent(conversationId)}`, { method: "DELETE" });
  const deletedCurrent = conversationId === state.currentConversationId;
  await loadConversations();
  if (deletedCurrent) {
    if (state.conversations.length) {
      await loadConversation(state.conversations[0].id);
    } else {
      state.currentConversationId = null;
      state.messages = [welcomeMessage];
      renderMessages();
    }
  }
  renderConversations();
  pushTrace("会话已删除");
}

async function ensureCurrentConversation() {
  if (state.currentConversationId) return state.currentConversationId;
  return createConversation(true);
}

async function refreshStatus() {
  const health = await apiJson("/api/health");
  const kb = await apiJson("/api/kb/status");
  const files = await apiJson("/api/kb/files");

  els.health.textContent = health.ready ? "系统已就绪" : "初始化中";
  els.health.className = `health-badge ${health.ready ? "ready" : "pending"}`;
  els.fileCount.textContent = kb.file_count;
  els.docCount.textContent = kb.document_count;
  els.vectorState.textContent = kb.rebuilding ? "重建中" : kb.needs_rebuild ? "待重建" : "已同步";
  els.lastRebuild.textContent = kb.last_rebuild_at || "not rebuilt";

  els.fileList.innerHTML = files.files.length
    ? files.files
        .map(
          (file) => `
            <div class="file-item">
              <div>
                <strong>${escapeHtml(file.name)}</strong>
                <span>${escapeHtml(file.extension)} &middot; ${formatSize(file.size)} &middot; ${escapeHtml(file.updated_at)}</span>
              </div>
              <button type="button" data-delete="${escapeHtml(file.name)}">删除</button>
            </div>
          `,
        )
        .join("")
    : `<div class="empty">知识库目录暂无可处理文件</div>`;
}

function parseSseBlock(block) {
  const lines = block.split("\n");
  let event = "message";
  const dataLines = [];

  for (const line of lines) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }

  return { event, data: JSON.parse(dataLines.join("\n") || "{}") };
}

async function sendMessage(message) {
  const sessionId = await ensureCurrentConversation();
  state.messages = state.messages === [welcomeMessage] ? [] : state.messages;
  if (state.messages.length === 1 && state.messages[0] === welcomeMessage) {
    state.messages = [];
  }

  state.messages.push({ role: "user", content: message });
  const assistantMessage = { role: "assistant", content: "" };
  state.messages.push(assistantMessage);
  renderMessages();
  pushTrace("请求已提交");

  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!response.ok || !response.body) {
    const error = await response.text();
    throw new Error(error || `HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let streamed = false;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      if (!part.trim()) continue;
      const { event, data } = parseSseBlock(part);
      if (event === "status") pushTrace(data.message || "状态更新");
      if (event === "trace") pushTrace(data.stage || "执行轨迹更新");
      if (event === "token") {
        streamed = true;
        assistantMessage.content += data.content || "";
        renderMessages();
      }
      if (event === "done") {
        state.lastResult = data;
        if (!streamed) assistantMessage.content = data.answer || "未生成回答";
        pushTrace("回答生成完成");
        renderMessages();
        await loadConversations();
      }
      if (event === "error") {
        assistantMessage.content = data.message || "请求失败";
        pushTrace(`错误：${assistantMessage.content}`);
        renderMessages();
      }
    }
  }
}

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = els.input.value.trim();
  if (!message) return;

  els.input.value = "";
  setBusy(true);
  try {
    await sendMessage(message);
    await refreshStatus();
  } catch (error) {
    state.messages.push({ role: "assistant", content: `请求失败：${error.message}` });
    pushTrace(`请求失败：${error.message}`);
    renderMessages();
  } finally {
    setBusy(false);
    els.input.focus();
  }
});

els.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    els.form.requestSubmit();
  }
});

els.newConversation.addEventListener("click", async () => {
  try {
    await createConversation(true);
  } catch (error) {
    pushTrace(`创建会话失败：${error.message}`);
  }
});

els.conversationList.addEventListener("click", async (event) => {
  const deleteButton = event.target.closest("[data-delete-conversation]");
  if (deleteButton) {
    await deleteConversation(deleteButton.dataset.deleteConversation);
    return;
  }

  const item = event.target.closest("[data-conversation-id]");
  if (!item) return;
  await loadConversation(item.dataset.conversationId);
});

els.refresh.addEventListener("click", async () => {
  try {
    await refreshStatus();
    await loadConversations();
    pushTrace("状态已刷新");
  } catch (error) {
    pushTrace(`状态刷新失败：${error.message}`);
  }
});

els.rebuild.addEventListener("click", async () => {
  try {
    els.kbMessage.textContent = "正在重建向量索引...";
    await apiJson("/api/kb/rebuild", { method: "POST" });
    els.kbMessage.textContent = "向量索引重建完成";
    pushTrace("知识库向量索引已重建");
    await refreshStatus();
  } catch (error) {
    els.kbMessage.textContent = error.message;
    pushTrace(`重建失败：${error.message}`);
  }
});

els.fileInput.addEventListener("change", async () => {
  if (!els.fileInput.files.length) return;
  const formData = new FormData();
  for (const file of els.fileInput.files) formData.append("files", file);

  try {
    els.kbMessage.textContent = "正在上传...";
    const response = await fetch("/api/kb/upload", { method: "POST", body: formData });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "上传失败");
    els.kbMessage.textContent = `已上传 ${data.saved.length} 个文件，请重新向量化`;
    pushTrace("知识库文件已上传");
    await refreshStatus();
  } catch (error) {
    els.kbMessage.textContent = error.message;
    pushTrace(`上传失败：${error.message}`);
  } finally {
    els.fileInput.value = "";
  }
});

els.fileList.addEventListener("click", async (event) => {
  const target = event.target.closest("[data-delete]");
  if (!target) return;
  const filename = target.dataset.delete;
  try {
    await apiJson(`/api/kb/files/${encodeURIComponent(filename)}`, { method: "DELETE" });
    els.kbMessage.textContent = `已删除 ${filename}，请重新向量化`;
    pushTrace(`知识库文件已删除：${filename}`);
    await refreshStatus();
  } catch (error) {
    els.kbMessage.textContent = error.message;
  }
});

els.copyTrace.addEventListener("click", async () => {
  await navigator.clipboard.writeText(els.traceLog.textContent);
  pushTrace("执行轨迹已复制");
});

async function init() {
  renderMessages();
  renderTrace();
  await loadConversations();
  if (state.conversations.length) {
    await loadConversation(state.conversations[0].id);
  } else {
    await createConversation(true);
  }
  await refreshStatus();
}

init().catch((error) => {
  els.health.textContent = "服务异常";
  els.health.className = "health-badge error";
  pushTrace(`启动状态检查失败：${error.message}`);
});
