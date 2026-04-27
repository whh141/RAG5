const { createApp, nextTick } = Vue;

createApp({
  data() {
    return {
      input: '',
      loading: false,
      activeTab: '链路',
      tabs: ['链路', '子问题', '证据', 'Trace', '知识库', '样例'],
      messages: [],
      lastResult: null,
      health: { ready: false },
      kbFiles: [],
      kbStatus: {
        rebuilding: false,
        needs_rebuild: false,
        last_rebuild_at: null,
        last_error: null,
        document_count: 0,
        file_count: 0,
        supported_extensions: [],
      },
      kbLoading: false,
      kbMessage: '',
      selectedUploadFiles: [],
      samples: [
        '学生证补办在哪里办？',
        '学生证补办在哪里办？\n它什么时候可以办？\n本周还能办吗？\n需要带什么材料？',
        '休学手续怎么办？\n需要经过哪些部门？\n这个流程一般要多久？\n本学期现在还能申请吗？',
        '成绩复核怎么申请？\n这个流程有时间限制吗？\n现在还能申请吗？',
        '帮我写一首歌',
      ],
    };
  },
  computed: {
    lastUserMessage() {
      for (let i = this.messages.length - 1; i >= 0; i -= 1) {
        if (this.messages[i].role === 'user') return this.messages[i].content;
      }
      return '';
    },
    summaryItems() {
      const result = this.lastResult;
      if (!result) {
        return [
          { label: '耗时', value: '-' },
          { label: '意图', value: '-' },
          { label: '路由', value: '-' },
          { label: '来源', value: '-' },
          { label: '引用', value: '-' },
          { label: '置信度', value: '-' },
        ];
      }
      return [
        { label: '耗时', value: `${result.elapsed_time.toFixed(2)}s` },
        { label: '意图', value: result.intent || '-' },
        { label: '路由', value: result.route || '-' },
        { label: '来源', value: result.answer_source || '-' },
        { label: '引用', value: String(result.citations?.length || 0) },
        { label: '置信度', value: Number(result.confidence || 0).toFixed(2) },
      ];
    },
    subResults() {
      return this.lastResult?.sub_results || [];
    },
    citations() {
      return this.lastResult?.citations || [];
    },
    evidenceItems() {
      return this.lastResult?.evidence_items || [];
    },
    traceText() {
      return JSON.stringify(this.lastResult?.trace || [], null, 2);
    },
    kbRebuilding() {
      return Boolean(this.kbStatus?.rebuilding);
    },
    kbSupportedText() {
      const extensions = this.kbStatus?.supported_extensions || [];
      return extensions.length ? extensions.join('、') : '-';
    },
  },
  mounted() {
    this.refreshHealth();
    this.loadKbStatus();
    this.loadKbFiles();
  },
  methods: {
    async refreshHealth() {
      const response = await fetch('/api/health');
      this.health = await response.json();
    },
    async send() {
      const message = this.input.trim();
      if (!message || this.loading || this.kbRebuilding) return;
      const history = this.messages.map((item) => ({ role: item.role, content: item.content }));
      this.messages.push({ role: 'user', content: message });
      this.messages.push({ role: 'assistant', content: '处理中...' });
      this.input = '';
      await this.scrollMessages();
      await this.callChat(message, history);
    },
    async retryLast() {
      if (this.loading || this.kbRebuilding || !this.lastUserMessage) return;
      let lastUserIndex = -1;
      for (let i = this.messages.length - 1; i >= 0; i -= 1) {
        if (this.messages[i].role === 'user') {
          lastUserIndex = i;
          break;
        }
      }
      if (lastUserIndex < 0) return;
      const message = this.messages[lastUserIndex].content;
      const history = this.messages.slice(0, lastUserIndex).map((item) => ({
        role: item.role,
        content: item.content,
      }));
      this.messages.splice(lastUserIndex);
      this.messages.push({ role: 'user', content: message });
      this.messages.push({ role: 'assistant', content: '处理中...' });
      await this.scrollMessages();
      await this.callChat(message, history);
    },
    clearChat() {
      this.messages = [];
      this.lastResult = null;
    },
    async callChat(message, history) {
      this.loading = true;
      try {
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message, history }),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || `HTTP ${response.status}`);
        }
        this.lastResult = data;
        this.messages[this.messages.length - 1] = {
          role: 'assistant',
          content: data.answer || '未生成有效回复。',
        };
        await this.refreshHealth();
        await this.loadKbStatus();
      } catch (error) {
        this.messages[this.messages.length - 1] = {
          role: 'assistant',
          content: `处理出错：${error.message}`,
        };
      } finally {
        this.loading = false;
        await this.scrollMessages();
      }
    },
    async loadKbStatus() {
      const response = await fetch('/api/kb/status');
      this.kbStatus = await response.json();
    },
    async loadKbFiles() {
      const response = await fetch('/api/kb/files');
      this.kbFiles = await response.json();
    },
    onKbFileChange(event) {
      this.selectedUploadFiles = Array.from(event.target.files || []);
    },
    async uploadKbFiles() {
      if (!this.selectedUploadFiles.length || this.kbLoading || this.kbRebuilding) return;
      this.kbLoading = true;
      this.kbMessage = '';
      try {
        const formData = new FormData();
        this.selectedUploadFiles.forEach((file) => formData.append('files', file));
        const response = await fetch('/api/kb/upload', {
          method: 'POST',
          body: formData,
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || `HTTP ${response.status}`);
        }
        this.kbMessage = `已上传：${data.saved.join('、')}。请重新向量化后生效。`;
        this.selectedUploadFiles = [];
        if (this.$refs.kbFileInput) this.$refs.kbFileInput.value = '';
        await this.loadKbStatus();
        await this.loadKbFiles();
      } catch (error) {
        this.kbMessage = `上传失败：${error.message}`;
      } finally {
        this.kbLoading = false;
      }
    },
    async deleteKbFile(name) {
      if (!name || this.kbLoading || this.kbRebuilding) return;
      this.kbLoading = true;
      this.kbMessage = '';
      try {
        const response = await fetch(`/api/kb/files/${encodeURIComponent(name)}`, {
          method: 'DELETE',
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || `HTTP ${response.status}`);
        }
        this.kbMessage = `已删除：${data.deleted}。请重新向量化后生效。`;
        await this.loadKbStatus();
        await this.loadKbFiles();
      } catch (error) {
        this.kbMessage = `删除失败：${error.message}`;
      } finally {
        this.kbLoading = false;
      }
    },
    async rebuildKb() {
      if (this.kbLoading || this.kbRebuilding) return;
      this.kbLoading = true;
      this.kbMessage = '正在重新向量化知识库...';
      try {
        const response = await fetch('/api/kb/rebuild', { method: 'POST' });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || `HTTP ${response.status}`);
        }
        this.kbStatus = data;
        this.kbMessage = `重新向量化完成，共 ${data.document_count} 个文档片段。`;
        await this.refreshHealth();
        await this.loadKbFiles();
      } catch (error) {
        this.kbMessage = `重新向量化失败：${error.message}`;
        await this.loadKbStatus();
      } finally {
        this.kbLoading = false;
      }
    },
    formatFileSize(size) {
      const value = Number(size || 0);
      if (value >= 1024 * 1024) return `${(value / 1024 / 1024).toFixed(2)} MB`;
      if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`;
      return `${value} B`;
    },
    async scrollMessages() {
      await nextTick();
      const box = this.$refs.messageBox;
      if (box) box.scrollTop = box.scrollHeight;
    },
    citationLocation(item) {
      if (item.url) return item.url;
      const parts = [];
      if (item.source_file) parts.push(item.source_file);
      if (item.page !== undefined && item.page !== null) parts.push(`第 ${item.page} 页`);
      if (item.chunk_id !== undefined && item.chunk_id !== null) parts.push(`片段 ${item.chunk_id}`);
      return parts.join('，') || item.source_type || '';
    },
    trimText(value, limit) {
      const text = String(value || '').replace(/\s+/g, ' ').trim();
      return text.length > limit ? `${text.slice(0, limit)}...` : text;
    },
    renderMarkdown(value) {
      const escaped = this.escapeHtml(String(value || ''));
      return escaped
        .replace(/\n{2,}/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/^/, '<p>')
        .replace(/$/, '</p>');
    },
    escapeHtml(value) {
      return value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    },
  },
}).mount('#app');
