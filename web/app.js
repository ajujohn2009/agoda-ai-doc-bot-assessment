// ==================== DOM Elements ====================
const chatWindow = document.getElementById('chatWindow');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const clearChatBtn = document.getElementById('clearChatBtn');
const sideLinks = document.querySelectorAll('.side-link');
const viewChat = document.getElementById('view-chat');
const viewUpload = document.getElementById('view-upload');
const mobileMenu = document.getElementById('mobileMenu');
const sidebar = document.querySelector('.sidebar');
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const uploadStatus = document.getElementById('uploadStatus');
const fileList = document.getElementById('fileList');
const docList = document.getElementById('docList');
const docCount = document.getElementById('docCount');
const modelSelect = document.getElementById('modelSelect');
const viewTitle = document.getElementById('viewTitle');
const viewSubtitle = document.getElementById('viewSubtitle');
const loadingOverlay = document.getElementById('loadingOverlay');
const themeToggle = document.getElementById('themeToggle');

// ==================== State Management ====================
let messages = [];
let pendingFiles = [];
let isStreaming = false;
let currentChatId = null; // 🔹 Track current conversation ID
let timestampUpdateInterval = null; // 🔹 Interval for updating timestamps

// ==================== Timestamp Formatting ====================
function formatTimestamp(isoString) {
  if (!isoString) return '';
  
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  // Just now (< 1 minute)
  if (diffMins < 1) {
    return 'Just now';
  }
  
  // Minutes ago (< 1 hour)
  if (diffMins < 60) {
    return `${diffMins} ${diffMins === 1 ? 'minute' : 'minutes'} ago`;
  }
  
  // Hours ago (< 24 hours)
  if (diffHours < 24) {
    return `${diffHours} ${diffHours === 1 ? 'hour' : 'hours'} ago`;
  }
  
  // Days ago (< 7 days)
  if (diffDays < 7) {
    return `${diffDays} ${diffDays === 1 ? 'day' : 'days'} ago`;
  }
  
  // Full date for older messages
  const options = { 
    month: 'short', 
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
  };
  return date.toLocaleDateString(undefined, options);
}

function formatFullTimestamp(isoString) {
  if (!isoString) return '';
  
  const date = new Date(isoString);
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

// ==================== Timestamp Auto-Update ====================
function updateAllTimestamps() {
  // Get all timestamp elements in the chat window
  const timestampElements = chatWindow.querySelectorAll('.message-timestamp');
  
  timestampElements.forEach(timestampEl => {
    const fullTimestamp = timestampEl.getAttribute('title');
    if (fullTimestamp) {
      // Parse the full timestamp to get the ISO string
      const isoString = timestampEl.getAttribute('data-timestamp');
      if (isoString) {
        // Update the relative time display
        timestampEl.textContent = formatTimestamp(isoString);
      }
    }
  });
}

function startTimestampUpdates() {
  // Clear any existing interval
  if (timestampUpdateInterval) {
    clearInterval(timestampUpdateInterval);
  }
  
  // Update timestamps every minute (60000ms)
  timestampUpdateInterval = setInterval(() => {
    updateAllTimestamps();
  }, 60000);
}

function stopTimestampUpdates() {
  if (timestampUpdateInterval) {
    clearInterval(timestampUpdateInterval);
    timestampUpdateInterval = null;
  }
}

// ==================== View Management ====================
function setActiveView(name) {
  sideLinks.forEach(btn => btn.classList.toggle('active', btn.dataset.view === name));
  viewChat.classList.toggle('hidden', name !== 'chat');
  viewUpload.classList.toggle('hidden', name !== 'upload');

  document.body.setAttribute('data-current-view', name);
  
  // Save current view to localStorage
  localStorage.setItem('docschat.currentView', name);

  if (name === 'chat') {
    viewTitle.textContent = 'AI Document Assistant';
    viewSubtitle.textContent = 'Ask questions about your uploaded documents';
    chatInput.focus();
  } else if (name === 'upload') {
    viewTitle.textContent = 'Document Management';
    viewSubtitle.textContent = 'Upload and manage your knowledge base';
  }

  if (sidebar.classList.contains('open')) {
    sidebar.classList.remove('open');
  }
}

// ==================== Theme Management ====================
function getTheme() {
  return localStorage.getItem('docschat.theme') || 'dark';
}

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('docschat.theme', theme);
}

function toggleTheme() {
  const currentTheme = getTheme();
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  setTheme(newTheme);
}

// ==================== Message Rendering ====================
function appendMsg(role, text, { markdown = false, timestamp = null } = {}) {
  const row = document.createElement('div');
  row.className = `message ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  
  if (role === 'user') {
    avatar.innerHTML = `<svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <circle cx="10" cy="7" r="3" stroke="currentColor" stroke-width="1.5"/>
      <path d="M4 17c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
    </svg>`;
  } else {
    avatar.innerHTML = `<svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <path d="M10 2C5.6 2 2 5.6 2 10s3.6 8 8 8 8-3.6 8-8-3.6-8-8-8zm0 14c-3.3 0-6-2.7-6-6s2.7-6 6-6 6 2.7 6 6-2.7 6-6 6z" fill="currentColor"/>
      <circle cx="7" cy="9" r="1.5" fill="currentColor"/>
      <circle cx="13" cy="9" r="1.5" fill="currentColor"/>
      <path d="M7 12c1 1.5 2 2 3 2s2-.5 3-2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
    </svg>`;
  }

  const contentWrapper = document.createElement('div');
  contentWrapper.className = 'message-content';

  const bubble = document.createElement('div');
  bubble.className = 'bubble chat-message';
  
  if (markdown) {
    bubble.innerHTML = marked.parse(text || '');
  } else {
    bubble.textContent = text || '';
  }

  contentWrapper.appendChild(bubble);

  // Add timestamp if provided
  if (timestamp) {
    const timestampEl = document.createElement('div');
    timestampEl.className = 'message-timestamp';
    timestampEl.textContent = formatTimestamp(timestamp);
    timestampEl.title = formatFullTimestamp(timestamp);
    timestampEl.setAttribute('data-timestamp', timestamp); // Store ISO timestamp for updates
    contentWrapper.appendChild(timestampEl);
  }

  row.appendChild(avatar);
  row.appendChild(contentWrapper);
  chatWindow.appendChild(row);
  
  smoothScrollToBottom();
  
  return bubble;
}

function smoothScrollToBottom() {
  chatWindow.scrollTo({
    top: chatWindow.scrollHeight,
    behavior: 'smooth'
  });
}

function addModelTag(bubbleEl, provider, modelName) {
  if (!provider || !modelName || !bubbleEl) return;

  const tag = document.createElement('div');
  tag.className = 'model-tag';
  
  const niceProvider =
    provider === 'openai' ? 'OpenAI' :
    provider === 'ollama' ? 'Ollama' :
    provider;
  
  tag.innerHTML = `<svg width="12" height="12" viewBox="0 0 12 12" fill="none" style="display: inline; vertical-align: middle; margin-right: 4px;">
    <circle cx="6" cy="6" r="5" stroke="currentColor" stroke-width="1"/>
    <circle cx="6" cy="6" r="2" fill="currentColor"/>
  </svg>Answered by ${niceProvider} — ${modelName}`;

  bubbleEl.appendChild(tag);
}

// ==================== Conversation Loading ====================
async function loadConversationHistory() {
  if (!currentChatId) {
    return false;
  }

  try {
    const res = await fetch(`/api/conversations/${currentChatId}`);
    
    if (!res.ok) {
      // Conversation doesn't exist anymore, clear the stored ID
      if (res.status === 404) {
        currentChatId = null;
        localStorage.removeItem('docschat.chatId');
      }
      return false;
    }

    const data = await res.json();
    const loadedMessages = data.messages || [];

    if (loadedMessages.length === 0) {
      return false;
    }

    // Clear current UI
    chatWindow.innerHTML = '';
    messages = [];

    // Render all messages with timestamps
    for (const msg of loadedMessages) {
      const role = msg.role === 'user' ? 'user' : 'bot';
      const bubble = appendMsg(role, msg.content, { 
        markdown: role === 'bot',
        timestamp: msg.created_at 
      });
      
      // For bot messages, add sources and model tag if available
      if (role === 'bot') {
        const sources = msg.sources || [];
        const hasGroundedSources = sources && sources.length > 0;
        
        // Add sources if available
        if (hasGroundedSources) {
          const sourcesHTML = `
            <div class="sources-divider"></div>
            <div class="sources-block">
              <div class="sources-title">Sources</div>
              <ul class="sources-list">
                ${sources.map((s, index) => `
                  <li class="source-item" data-source-index="${index}">
                    <div class="source-header">
                      <span class="file-icon">
                        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <path d="M8 1H3a2 2 0 00-2 2v8a2 2 0 002 2h6a2 2 0 002-2V5l-3-4z" stroke="currentColor" stroke-width="1.5"/>
                          <path d="M8 1v4h3" stroke="currentColor" stroke-width="1.5"/>
                        </svg>
                      </span>
                      <span class="source-filename">${s.filename}</span>
                      <span class="source-score">(relevance: ${s.score})</span>
                      ${s.preview ? `
                        <button class="expand-btn" onclick="toggleSourcePreview(this)" aria-label="Show excerpt">
                          <svg class="chevron-icon" width="16" height="16" viewBox="0 0 16 16" fill="none">
                            <path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                          </svg>
                        </button>
                      ` : ''}
                    </div>
                    ${s.preview ? `<div class="source-preview collapsed">"${s.preview}"</div>` : ''}
                  </li>
                `).join('')}
              </ul>
            </div>
          `;
          bubble.innerHTML += sourcesHTML;
        }
        
        // Add model tag if available
        if (msg.model_provider && msg.model_name) {
          addModelTag(bubble, msg.model_provider, msg.model_name);
        }
      }
      
      // Store in memory
      messages.push({
        role: role,
        text: msg.content,
        timestamp: msg.created_at
      });
    }

    console.log(`✅ Loaded ${loadedMessages.length} messages from conversation ${currentChatId}`);
    return true;

  } catch (err) {
    console.error('Failed to load conversation:', err);
    return false;
  }
}

// ==================== File Management ====================
function renderFilesList() {
  fileList.innerHTML = '';
  if (!pendingFiles.length) return;

  const ul = document.createElement('ul');
  pendingFiles.forEach((f, i) => {
    const li = document.createElement('li');
    
    const fileInfo = document.createElement('span');
    fileInfo.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" style="display: inline-block; vertical-align: middle; margin-right: 6px;">
      <path d="M9 1H4a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V6l-5-5z" stroke="currentColor" stroke-width="1.5"/>
      <path d="M9 1v5h5" stroke="currentColor" stroke-width="1.5"/>
    </svg>${f.name} <span style="opacity: 0.6;">(${(f.size / 1024).toFixed(1)} KB)</span>`;
    
    const removeBtn = document.createElement('button');
    removeBtn.innerHTML = '×';
    removeBtn.title = 'Remove from queue';
    removeBtn.onclick = () => {
      pendingFiles.splice(i, 1);
      renderFilesList();
    };
    
    li.appendChild(fileInfo);
    li.appendChild(removeBtn);
    ul.appendChild(li);
  });
  
  fileList.appendChild(ul);
}

// ==================== Model Management ====================
async function loadModels() {
  try {
    const res = await fetch('/api/models');
    const data = await res.json();
    const opts = [];
    
    (data.openai || []).forEach(m => opts.push({ 
      label: `OpenAI - ${m}`, 
      value: `openai:${m}` 
    }));
    
    (data.ollama || []).forEach(m => opts.push({ 
      label: `Ollama - ${m}`, 
      value: `ollama:${m}` 
    }));
    
    modelSelect.innerHTML = '';
    
    if (opts.length === 0) {
      modelSelect.innerHTML = '<option>No models available</option>';
      return;
    }
    
    opts.forEach(o => {
      const opt = document.createElement('option');
      opt.value = o.value;
      opt.textContent = o.label;
      modelSelect.appendChild(opt);
    });
    
    const saved = localStorage.getItem('docschat.model');
    if (saved && [...modelSelect.options].some(x => x.value === saved)) {
      modelSelect.value = saved;
    }
    
    modelSelect.addEventListener('change', () => {
      localStorage.setItem('docschat.model', modelSelect.value);
    });
  } catch (e) {
    console.error('Error loading models:', e);
    modelSelect.innerHTML = '<option>Error loading models</option>';
  }
}

// ==================== Document Management ====================
function showLoading() {
  loadingOverlay?.classList.remove('hidden');
}

function hideLoading() {
  loadingOverlay?.classList.add('hidden');
}

function showStatus(msg, type = 'info') {
  uploadStatus.textContent = msg;
  uploadStatus.className = `upload-status ${type}`;
  setTimeout(() => {
    uploadStatus.textContent = '';
    uploadStatus.className = 'upload-status';
  }, 5000);
}

async function refreshDocs() {
  try {
    const res = await fetch('/api/documents');
    if (!res.ok) throw new Error('Failed to fetch documents');
    
    const docs = await res.json();
    docCount.textContent = `${docs.length} ${docs.length === 1 ? 'document' : 'documents'}`;
    
    if (docs.length === 0) {
      docList.innerHTML = `
        <div class="empty-state">
          <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
            <rect width="64" height="64" rx="32" fill="rgba(148, 163, 184, 0.1)"/>
            <path d="M24 20h16a4 4 0 014 4v16a4 4 0 01-4 4H24a4 4 0 01-4-4V24a4 4 0 014-4z" stroke="#94a3b8" stroke-width="2"/>
            <path d="M28 28h8M28 32h8M28 36h5" stroke="#94a3b8" stroke-width="2" stroke-linecap="round"/>
          </svg>
          <p>No documents uploaded yet</p>
          <p class="empty-subtitle">Upload your first document to get started</p>
        </div>
      `;
      return;
    }
    
    docList.innerHTML = docs.map(doc => {
      const uploadDate = new Date(doc.uploaded_at);
      const formattedDate = uploadDate.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
      });
      
      return `
        <div class="doc-item" data-doc-id="${doc.id}">
          <div class="doc-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z" stroke="currentColor" stroke-width="2"/>
              <path d="M14 2v6h6" stroke="currentColor" stroke-width="2"/>
              <path d="M10 13h4M10 17h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
          </div>
          <div class="doc-info">
            <div class="doc-name" title="${doc.filename}">${doc.filename}</div>
            <div class="doc-meta">
              <span>${doc.num_chunks} chunks</span>
              <span class="doc-divider">•</span>
              <span>${(doc.size_bytes / 1024).toFixed(1)} KB</span>
              <span class="doc-divider">•</span>
              <span>${formattedDate}</span>
            </div>
          </div>
          <button class="doc-delete" data-doc-id="${doc.id}" title="Delete document">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M2 4h12M5 4V3a1 1 0 011-1h4a1 1 0 011 1v1M12 4v9a1 1 0 01-1 1H5a1 1 0 01-1-1V4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
      `;
    }).join('');
    
    // Attach delete handlers
    document.querySelectorAll('.doc-delete').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const docId = btn.dataset.docId;
        
        if (!confirm('Are you sure you want to delete this document?')) return;
        
        try {
          showLoading();
          const res = await fetch(`/api/documents/${docId}`, { method: 'DELETE' });
          if (!res.ok) throw new Error('Delete failed');
          
          showStatus('✓ Document deleted successfully', 'success');
          await refreshDocs();
        } catch (err) {
          console.error('Delete error:', err);
          showStatus('✗ Failed to delete document', 'error');
        } finally {
          hideLoading();
        }
      });
    });
  } catch (e) {
    console.error('Error refreshing docs:', e);
  }
}

// ==================== Event Listeners ====================

// Theme toggle
themeToggle.addEventListener('click', toggleTheme);

// Clear chat
clearChatBtn.addEventListener('click', async () => {
  if (!confirm('Clear this conversation? This will delete all messages.')) return;
  
  // Delete conversation from backend if it exists
  if (currentChatId) {
    try {
      await fetch(`/api/conversations/${currentChatId}`, { method: 'DELETE' });
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  }
  
  // Clear frontend state
  chatWindow.innerHTML = '';
  messages = [];
  currentChatId = null;
  localStorage.removeItem('docschat.chatId');
  
  // Show welcome message
  appendMsg(
    'bot',
    'Hello! I\'m your AI document assistant. Upload documents and ask me anything about them.',
    { markdown: true, timestamp: new Date().toISOString() }
  );
});

// Mobile menu
mobileMenu?.addEventListener('click', () => {
  sidebar.classList.toggle('open');
});

// Side navigation
sideLinks.forEach(link => {
  link.addEventListener('click', () => {
    const view = link.dataset.view;
    setActiveView(view);
    
    if (view === 'upload') {
      refreshDocs();
    }
  });
});

// Drag & drop
// dropzone.addEventListener('click', () => fileInput.click());

dropzone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropzone.classList.add('hover');
});

dropzone.addEventListener('dragleave', () => {
  dropzone.classList.remove('hover');
});

dropzone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropzone.classList.remove('hover');
  
  const files = [...e.dataTransfer.files];
  const validFiles = files.filter(f => {
    const ext = f.name.split('.').pop().toLowerCase();
    return ['pdf', 'docx', 'txt'].includes(ext);
  });
  
  if (validFiles.length < files.length) {
    showStatus('Some files were skipped. Only PDF, DOCX, and TXT files are supported.', 'error');
  }
  
  pendingFiles.push(...validFiles);
  renderFilesList();
});

fileInput.addEventListener('change', () => {
  pendingFiles.push(...fileInput.files);
  fileInput.value = '';
  renderFilesList();
});

uploadBtn.addEventListener('click', async () => {
  if (!pendingFiles.length) {
    showStatus('Please select files to upload', 'error');
    return;
  }
  
  const fd = new FormData();
  pendingFiles.forEach(f => fd.append('files', f));
  
  showLoading();
  uploadStatus.textContent = 'Uploading and processing documents...';
  
  try {
    const res = await fetch('/api/documents/upload', { method: 'POST', body: fd });
    if (!res.ok) throw new Error('Upload failed');
    
    showStatus('✓ Documents uploaded and indexed successfully', 'success');
    pendingFiles = [];
    renderFilesList();
    await refreshDocs();
  } catch (e) {
    console.error('Upload error:', e);
    showStatus('✗ Upload failed. Please try again.', 'error');
  } finally {
    hideLoading();
  }
});

// Chat input
chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(200, chatInput.scrollHeight) + 'px';
});

chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    chatForm.requestSubmit();
  }
});

// Chat submission with streaming
chatForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const q = chatInput.value.trim();
  if (!q || isStreaming) return;
  
  chatInput.value = '';
  chatInput.style.height = '44px';
  
  const userTimestamp = new Date().toISOString();
  
  messages.push({ role: 'user', text: q, timestamp: userTimestamp });
  appendMsg('user', q, { timestamp: userTimestamp });
  
  const bubble = appendMsg('bot', '', { markdown: true });
  let full = '';
  const chosenModel = modelSelect?.value || null;
  
  const history = messages.slice(-6).map(m => ({
    role: m.role === 'bot' ? 'assistant' : 'user',
    content: m.text
  }));
  
  isStreaming = true;
  
  try {
    const res = await fetch('/api/ask_stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: q,
        history,
        top_k: 5,
        min_score: 0.45,
        model: chosenModel,
        chat_id: currentChatId || null
      })
    });
    
    if (!res.ok || !res.body) {
      bubble.innerHTML = marked.parse('⚠️ The server could not complete the request. Please try again.');
      messages.push({ role: 'bot', text: 'The server could not complete the request.', timestamp: new Date().toISOString() });
      return;
    }
    
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let assistantTimestamp = null;
    
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop();
      
      for (const part of parts) {
        const line = part.trim().startsWith('data:') ? part.trim().slice(5).trim() : null;
        if (!line) continue;
        
        let data;
        try { 
          data = JSON.parse(line); 
        } catch { 
          continue; 
        }
        
        if (data.type === 'delta') {
          full += data.text || '';
          bubble.innerHTML = marked.parse(full);
          smoothScrollToBottom();
          
        } else if (data.type === 'final') {
          full = data.text || full;
          const grounded = !!data.grounded;
          const sources = Array.isArray(data.sources) ? data.sources : [];
          assistantTimestamp = data.timestamp || new Date().toISOString();
          
          bubble.innerHTML = marked.parse(full);
          
          if (grounded && sources.length) {
            const sourcesHTML = `
              <div class="sources-divider"></div>
              <div class="sources-block">
                <div class="sources-title">Sources</div>
                <ul class="sources-list">
                  ${sources.map((s, index) => `
                    <li class="source-item" data-source-index="${index}">
                      <div class="source-header">
                        <span class="file-icon">
                          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                            <path d="M8 1H3a2 2 0 00-2 2v8a2 2 0 002 2h6a2 2 0 002-2V5l-3-4z" stroke="currentColor" stroke-width="1.5"/>
                            <path d="M8 1v4h3" stroke="currentColor" stroke-width="1.5"/>
                          </svg>
                        </span>
                        <span class="source-filename">${s.filename}</span>
                        <span class="source-score">(relevance: ${s.score})</span>
                        ${s.preview ? `
                          <button class="expand-btn" onclick="toggleSourcePreview(this)" aria-label="Show excerpt">
                            <svg class="chevron-icon" width="16" height="16" viewBox="0 0 16 16" fill="none">
                              <path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                            </svg>
                          </button>
                        ` : ''}
                      </div>
                      ${s.preview ? `<div class="source-preview collapsed">"${s.preview}"</div>` : ''}
                    </li>
                  `).join('')}
                </ul>
              </div>
            `;
            bubble.innerHTML += sourcesHTML;
          }
          
          if (data.model_provider && data.model_name) {
            addModelTag(bubble, data.model_provider, data.model_name);
          }

          // Add timestamp to assistant message
          if (assistantTimestamp) {
            const timestampEl = document.createElement('div');
            timestampEl.className = 'message-timestamp';
            timestampEl.textContent = formatTimestamp(assistantTimestamp);
            timestampEl.title = formatFullTimestamp(assistantTimestamp);
            timestampEl.setAttribute('data-timestamp', assistantTimestamp); // Store ISO timestamp for updates
            bubble.parentElement.appendChild(timestampEl);
          }

          // 🔹 Capture conversation id from backend
          if (data.conversation_id) {
            currentChatId = data.conversation_id;
            localStorage.setItem('docschat.chatId', String(currentChatId));
            console.log(`✅ Saved conversation ID: ${currentChatId}`);
          }
          
          messages.push({ role: 'bot', text: full, timestamp: assistantTimestamp });
          
        } else if (data.type === 'done') {
          // Stream complete
        }
      }
    }
  } catch (err) {
    console.error('Chat error:', err);
    bubble.innerHTML = marked.parse('⚠️ Network error. Please check your connection and try again.');
    messages.push({ role: 'bot', text: 'Network error contacting the server.', timestamp: new Date().toISOString() });
  } finally {
    isStreaming = false;
  }
});

// ==================== Initialization ====================
window.addEventListener('load', async () => {
  setTheme(getTheme());
  
  // 🔹 Start timestamp auto-update interval
  startTimestampUpdates();
  
  // 🔹 Restore chat id if exists
  const savedChatId = localStorage.getItem('docschat.chatId');
  if (savedChatId) {
    const parsed = parseInt(savedChatId, 10);
    if (!Number.isNaN(parsed)) {
      currentChatId = parsed;
      console.log(`📖 Found saved conversation ID: ${currentChatId}`);
    }
  }

  showLoading();
  
  try {
    await Promise.all([loadModels(), refreshDocs()]);
    
    // 🔹 Restore the last active view (default to 'chat')
    const savedView = localStorage.getItem('docschat.currentView') || 'chat';
    setActiveView(savedView);
    
    // 🔹 Try to load conversation history (only if on chat view)
    if (savedView === 'chat') {
      const historyLoaded = await loadConversationHistory();
      
      // Only show welcome message if no history was loaded
      if (!historyLoaded) {
        appendMsg(
          'bot',
          'Hello! I\'m your AI document assistant. Upload documents and ask me anything about them. I can help you understand, analyze, and extract information from your files.',
          { markdown: true, timestamp: new Date().toISOString() }
        );
      }
    }
  } catch (err) {
    console.error('Initialization error:', err);
  } finally {
    hideLoading();
  }
});

// Handle window resize
let resizeTimeout;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimeout);
  resizeTimeout = setTimeout(() => {
    if (window.innerWidth > 768 && sidebar.classList.contains('open')) {
      sidebar.classList.remove('open');
    }
  }, 250);
});

// Cleanup timestamp updates when page unloads
window.addEventListener('beforeunload', () => {
  stopTimestampUpdates();
});

// ==================== Source Preview Toggle ====================

/**
 * Toggle source preview visibility
 * @param {HTMLElement} button - The expand button that was clicked
 */
function toggleSourcePreview(button) {
  const sourceItem = button.closest('.source-item');
  const preview = sourceItem.querySelector('.source-preview');
  const chevron = button.querySelector('.chevron-icon');
  
  if (preview.classList.contains('collapsed')) {
    // Expand
    preview.classList.remove('collapsed');
    preview.classList.add('expanded');
    chevron.style.transform = 'rotate(180deg)';
    button.setAttribute('aria-label', 'Hide excerpt');
  } else {
    // Collapse
    preview.classList.remove('expanded');
    preview.classList.add('collapsed');
    chevron.style.transform = 'rotate(0deg)';
    button.setAttribute('aria-label', 'Show excerpt');
  }
}

// Make function globally available
window.toggleSourcePreview = toggleSourcePreview;