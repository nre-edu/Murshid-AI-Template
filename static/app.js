// مرشد — مساعدك المعرفي | المحرك البرمجي للواجهة (إصدار الأدلة المحلية المعتمدة)
document.addEventListener('DOMContentLoaded', () => {
  // Application State
  const state = {
    chatHistory: [],
    isGenerating: false,
    abortController: null,
    systemStatus: null,
    branding: null,
    hasSentFirstMessage: false,
    currentViewingSourceText: '',
    questionRow: null
  };

  // Everything interpolated into innerHTML goes through this
  function esc(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // DOM Elements
  const heroSection = document.getElementById('heroSection');
  const compactBanner = document.getElementById('compactBanner');
  const expandHeroBtn = document.getElementById('expandHeroBtn');
  const startChatBtn = document.getElementById('startChatBtn');
  const queryInput = document.getElementById('queryInput');
  const chatForm = document.getElementById('chatForm');
  const sendBtn = document.getElementById('sendBtn');
  const stopGenerationBtn = document.getElementById('stopGenerationBtn');
  const messagesContainer = document.getElementById('messagesContainer');
  const emptyState = document.getElementById('emptyState');
  const thinkingIndicator = document.getElementById('thinkingIndicator');
  const newChatBtn = document.getElementById('newChatBtn');

  // Status Badges
  const heroStatusPill = document.getElementById('heroStatusPill');
  const heroStatusDot = document.getElementById('heroStatusDot');
  const heroStatusText = document.getElementById('heroStatusText');

  const chatCardStatusPill = document.getElementById('chatCardStatusPill');
  const chatCardStatusDot = document.getElementById('chatCardStatusDot');
  const chatCardStatusText = document.getElementById('chatCardStatusText');
  const chatSourcesCount = document.getElementById('chatSourcesCount');

  // Drawer Elements
  const openSourcesBtn = document.getElementById('openSourcesBtn');
  const toggleSourcesInChatBtn = document.getElementById('toggleSourcesInChatBtn');
  const closeDrawerBtn = document.getElementById('closeDrawerBtn');
  const sourcesDrawer = document.getElementById('sourcesDrawer');
  const sourcesDrawerBackdrop = document.getElementById('sourcesDrawerBackdrop');
  const drawerStatusPill = document.getElementById('drawerStatusPill');
  const drawerStatusDot = document.getElementById('drawerStatusDot');
  const drawerStatusLabel = document.getElementById('drawerStatusLabel');
  const drawerFilesCount = document.getElementById('drawerFilesCount');
  const drawerChunksCount = document.getElementById('drawerChunksCount');
  const drawerFilesCountBadge = document.getElementById('drawerFilesCountBadge');
  const drawerLastSync = document.getElementById('drawerLastSync');
  const drawerFilesList = document.getElementById('drawerFilesList');

  // Source Viewer Modal Elements
  const sourceViewerModal = document.getElementById('sourceViewerModal');
  const closeSourceViewerBtn = document.getElementById('closeSourceViewerBtn');
  const sourceViewerTitle = document.getElementById('sourceViewerTitle');
  const sourceViewerSubtitle = document.getElementById('sourceViewerSubtitle');
  const sourceViewerMeta = document.getElementById('sourceViewerMeta');
  const sourceViewerContent = document.getElementById('sourceViewerContent');
  const copySourceTextBtn = document.getElementById('copySourceTextBtn');

  // Setup modal (AI key instructions — no secret forms)
  const adminTriggerBtn = document.getElementById('adminTriggerBtn');
  const adminModal = document.getElementById('adminModal');
  const closeAdminModalBtn = document.getElementById('closeAdminModalBtn');
  const toastContainer = document.getElementById('toastContainer');

  // ==========================================
  // Toast Helper
  // ==========================================
  function showToast(message, duration = 3200) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    toastContainer.appendChild(toast);
    
    requestAnimationFrame(() => toast.classList.add('show'));
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  // ==========================================
  // Fetch Real Status & Sources
  // ==========================================
  async function fetchStatus() {
    try {
      const res = await fetch('/api/status');
      if (!res.ok) throw new Error('فشل جلب حالة الخادم');
      const data = await res.json();
      state.systemStatus = data;
      renderStatusBadges(data);
      // Setup help is for the site owner; visitors never need it once the key is set
      if (adminTriggerBtn) adminTriggerBtn.hidden = Boolean(data.has_gemini_key);
    } catch (err) {
      console.error('[Status error]', err);
      renderStatusBadges({
        status: 'error',
        label: 'تعذر الاتصال بالخادم',
        documents_count: 0
      });
    }
  }

  function renderStatusBadges(stat) {
    const isReady = stat.status === 'ready';
    const statusClass = isReady ? 'connected' : 'incomplete';
    const label = stat.label || 'جاري الفحص...';
    const docsCount = stat.documents_count || 0;
    const chunksCount = stat.chunks_count || 0;

    if (heroStatusPill && heroStatusDot && heroStatusText) {
      heroStatusPill.className = `status-pill ${statusClass}`;
      heroStatusDot.className = `status-dot ${statusClass}`;
      heroStatusText.textContent = label;
    }

    if (chatCardStatusPill && chatCardStatusDot && chatCardStatusText) {
      chatCardStatusPill.className = `status-pill ${statusClass}`;
      chatCardStatusDot.className = `status-dot ${statusClass}`;
      chatCardStatusText.textContent = label;
    }

    if (chatSourcesCount) {
      chatSourcesCount.textContent = docsCount;
    }

    if (drawerStatusPill && drawerStatusDot && drawerStatusLabel) {
      drawerStatusPill.className = `status-pill ${statusClass}`;
      drawerStatusDot.className = `status-dot ${statusClass}`;
      drawerStatusLabel.textContent = isReady ? 'مفهرس وجاهز' : 'يتطلب إكمال الإعداد';
    }

    if (drawerFilesCount) drawerFilesCount.textContent = `${docsCount} أدلة معتمدة`;
    if (drawerChunksCount) drawerChunksCount.textContent = `${chunksCount} مقطع`;
    if (drawerFilesCountBadge) drawerFilesCountBadge.textContent = `${docsCount} دليل`;
    if (drawerLastSync && stat.last_indexed) drawerLastSync.textContent = stat.last_indexed;
  }

  async function fetchSources() {
    try {
      const res = await fetch('/api/sources');
      if (!res.ok) return;
      const data = await res.json();
      renderDrawerFiles(data.documents || []);
    } catch (e) {
      console.error('[Sources error]', e);
    }
  }

  function renderDrawerFiles(documents) {
    if (!drawerFilesList) return;
    drawerFilesList.innerHTML = '';

    if (!documents || documents.length === 0) {
      drawerFilesList.innerHTML = `
        <div style="background:#F8FAFC; border:1px dashed #CBD5E1; border-radius:0.75rem; padding:1.25rem; text-align:center; font-size:0.88rem; color:var(--color-charcoal-muted);">
          لا توجد أدلة مفهرسة حالياً في مجلد Knowledge/.
        </div>
      `;
      return;
    }

    documents.forEach(doc => {
      const item = document.createElement('div');
      item.className = 'drawer-file-item';
      
      const sizeKb = doc.file_size ? Math.round(doc.file_size / 1024) : 0;
      const dateStr = doc.release_date ? `تاريخ: ${doc.release_date}` : '';
      const versionStr = doc.version ? ` • ${doc.version}` : '';

      item.innerHTML = `
        <div class="file-item-info">
          <div style="color:#FF6B35; flex-shrink:0;">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
            </svg>
          </div>
          <div style="overflow:hidden;">
            <div class="file-name-txt" title="${esc(doc.title)}">${esc(doc.title)}</div>
            <div style="font-size:0.75rem; color:var(--color-charcoal-muted);">
              ${esc(doc.sections_count)} مقطع • ${sizeKb} ك.ب ${esc(versionStr)}
            </div>
            ${dateStr ? `<div style="font-size:0.72rem; color:#64748B;">${esc(dateStr)}</div>` : ''}
          </div>
        </div>
        <div class="status-pill connected" style="font-size:0.75rem; padding:0.15rem 0.5rem; flex-shrink:0;">
          ${doc.demo ? 'تجريبي' : 'معتمد'}
        </div>
      `;
      drawerFilesList.appendChild(item);
    });
  }

  // Drawer Toggling
  function openDrawer() {
    sourcesDrawer.classList.add('active');
    sourcesDrawerBackdrop.classList.add('active');
    fetchSources();
  }
  function closeDrawer() {
    sourcesDrawer.classList.remove('active');
    sourcesDrawerBackdrop.classList.remove('active');
  }

  if (openSourcesBtn) openSourcesBtn.addEventListener('click', openDrawer);
  if (toggleSourcesInChatBtn) toggleSourcesInChatBtn.addEventListener('click', openDrawer);
  if (closeDrawerBtn) closeDrawerBtn.addEventListener('click', closeDrawer);
  if (sourcesDrawerBackdrop) sourcesDrawerBackdrop.addEventListener('click', closeDrawer);

  // ==========================================
  // Hero Condensation
  // ==========================================
  function collapseHero() {
    if (!state.hasSentFirstMessage) {
      state.hasSentFirstMessage = true;
      heroSection.classList.add('collapsed');
      compactBanner.classList.add('visible');
    }
  }

  if (expandHeroBtn) {
    expandHeroBtn.addEventListener('click', () => {
      heroSection.classList.toggle('collapsed');
      const isCollapsed = heroSection.classList.contains('collapsed');
      expandHeroBtn.querySelector('span').textContent = isCollapsed ? 'عرض التفاصيل' : 'تصغير';
    });
  }

  if (startChatBtn) {
    startChatBtn.addEventListener('click', () => {
      queryInput.focus();
      document.getElementById('chat').scrollIntoView({ behavior: 'smooth' });
    });
  }

  queryInput.addEventListener('input', () => {
    queryInput.style.height = 'auto';
    queryInput.style.height = `${Math.min(queryInput.scrollHeight, 130)}px`;
  });

  queryInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event('submit'));
    }
  });

  function bindSuggestionChips() {
    document.querySelectorAll('.suggestion-chip').forEach(chip => {
      if (chip.dataset.bound === '1') return;
      chip.dataset.bound = '1';
      chip.addEventListener('click', async () => {
        if (chip.getAttribute('data-demo-map') === '1') {
          await loadDemoAnswerMap();
          return;
        }
        const q = chip.getAttribute('data-query');
        if (q) {
          queryInput.value = q;
          chatForm.dispatchEvent(new Event('submit'));
        }
      });
    });
  }

  const CHIP_ICONS = [
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>'
  ];

  function setTextContent(id, text) {
    const el = document.getElementById(id);
    if (el && text != null && String(text).trim() !== '') {
      el.textContent = text;
    }
  }

  function applyBranding(b) {
    if (!b || typeof b !== 'object') return;
    state.branding = b;

    if (b.page_title) document.title = b.page_title;
    const meta = document.querySelector('meta[name="description"]');
    if (meta && b.description) meta.setAttribute('content', b.description);

    setTextContent('brandLogoText', b.product_name);
    setTextContent('brandTagline', b.tagline);
    const brandLink = document.getElementById('brandLogoLink');
    if (brandLink) {
      brandLink.setAttribute('aria-label', `الرئيسية - ${b.product_name || 'مرشد'}`);
    }

    if (b.logo_url) {
      const logoHost = document.getElementById('brandLogoIcon');
      if (logoHost) {
        const img = document.createElement('img');
        img.src = b.logo_url;
        img.alt = '';
        logoHost.replaceChildren(img);
        logoHost.classList.add('has-image');
      }
      const favicon = document.querySelector('link[rel="icon"]');
      if (favicon) {
        favicon.removeAttribute('type');
        favicon.href = b.logo_url;
      }
    }

    const heroTitle = document.getElementById('heroTitle');
    if (heroTitle && b.hero_title_html) heroTitle.innerHTML = b.hero_title_html;
    setTextContent('heroDescription', b.hero_description);
    setTextContent('compactBannerText', b.compact_banner);
    setTextContent('assistantName', b.assistant_name || b.variant_name || b.product_name);

    const chatCard = document.getElementById('chatCard');
    if (chatCard) {
      const name = b.assistant_name || b.variant_name || b.product_name || 'مرشد';
      chatCard.setAttribute('aria-label', `منطقة المحادثة مع ${name}`);
    }

    setTextContent('emptyTitle', b.welcome_title);
    setTextContent('emptyDesc', b.welcome_message);
    setTextContent('suggestionsTitle', b.suggestions_title);
    setTextContent('howItWorksTitle', b.how_it_works_title);
    setTextContent('footerBrand', b.footer_brand);
    setTextContent('footerDisclaimer', b.footer_disclaimer);

    if (queryInput && b.input_placeholder) {
      queryInput.placeholder = b.input_placeholder;
    }

    const chipsHost = document.getElementById('suggestionsChips');
    const questions = Array.isArray(b.suggested_questions) ? b.suggested_questions : [];
    const demoBtn = document.getElementById('demoAnswerMapBtn');
    if (demoBtn) demoBtn.hidden = !b.show_demo_map;
    const suggestionsBlock = document.getElementById('suggestionsTitle');
    if (suggestionsBlock) suggestionsBlock.hidden = !questions.length && !b.show_demo_map;
    if (chipsHost && questions.length) {
      chipsHost.querySelectorAll('.suggestion-chip:not([data-demo-map])').forEach(el => el.remove());
      const frag = document.createDocumentFragment();
      questions.forEach((item, idx) => {
        const query = (item && item.query) ? String(item.query).trim() : '';
        if (!query) return;
        const label = (item && item.label) ? String(item.label).trim() : query.slice(0, 48);
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'suggestion-chip';
        btn.setAttribute('data-query', query);
        btn.innerHTML = `${CHIP_ICONS[idx % CHIP_ICONS.length]}<span></span>`;
        btn.querySelector('span').textContent = label;
        frag.appendChild(btn);
      });
      if (demoBtn) {
        chipsHost.insertBefore(frag, demoBtn);
      } else {
        chipsHost.appendChild(frag);
      }
      bindSuggestionChips();
    }
  }

  async function fetchBranding() {
    try {
      const res = await fetch('/api/branding');
      if (!res.ok) throw new Error('فشل جلب الهوية');
      const data = await res.json();
      applyBranding(data);
    } catch (err) {
      console.error('[Branding error]', err);
    }
  }

  bindSuggestionChips();

  async function loadDemoAnswerMap() {
    try {
      collapseHero();
      showToast('تحميل عينة توضيحية لخريطة الإجابة...');
      const res = await fetch('/api/demo/answer-map');
      if (!res.ok) throw new Error('تعذر تحميل العينة');
      const data = await res.json();

      if (emptyState) emptyState.style.display = 'none';
      state.questionRow = appendMessage('user', data.query || 'معاينة خريطة الإجابة').row;
      const { bubble } = appendMessage('assistant', '');
      const demoCitations = (data.answer_map && data.answer_map.sources || []).map((s, i) => ({
        citation_id: i + 1,
        doc_id: 'demo',
        chunk_id: s.id,
        doc_title: s.title,
        section_title: 'عينة توضيحية',
        excerpt: s.excerpt,
        page: null
      }));
      bubble.innerHTML = formatMarkdown(data.answer_text || '', demoCitations);
      const mapEl = renderAnswerMapCard(data.answer_map, demoCitations);
      if (mapEl) {
        bubble.appendChild(mapEl);
        // auto-open demo map
        const card = mapEl.querySelector('.answer-map-card');
        const btn = mapEl.querySelector('.btn-show-answer-map span');
        if (card) card.classList.remove('hidden');
        if (btn) btn.textContent = 'إخفاء خريطة الإجابة';
      }
      addMessageFooter(bubble, data.answer_text || '');
      focusChat();
      showToast('عينة توضيحية — ليست إجابة من أدلتك');
    } catch (e) {
      showToast(`خطأ: ${e.message}`);
    }
  }

  // ==========================================
  // Markdown Formatter
  // ==========================================
  function formatMarkdown(text, citations) {
    if (!text) return '';
    let html = text;

    html = html.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    html = html.replace(/^### (.*$)/gim, '<h4 style="font-size:1rem; font-weight:700; color:var(--color-charcoal-dark); margin:0.6rem 0 0.3rem 0;">$1</h4>');
    html = html.replace(/^## (.*$)/gim, '<h3 style="font-size:1.1rem; font-weight:800; color:var(--color-charcoal-dark); margin:0.8rem 0 0.4rem 0;">$1</h3>');
    html = html.replace(/^# (.*$)/gim, '<h2 style="font-size:1.25rem; font-weight:800; color:var(--color-charcoal-dark); margin:1rem 0 0.5rem 0;">$1</h2>');

    html = html.replace(/\*\*(.*?)\*\*/gim, '<strong style="color:var(--color-charcoal-dark);">$1</strong>');
    html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');
    html = html.replace(/`([^`]+)`/gim, '<code>$1</code>');
    html = html.replace(/^\s*[-*]\s+(.*$)/gim, '<li style="margin-bottom:0.25rem;">$1</li>');
    html = html.replace(/(<li.*<\/li>)/gms, '<ul style="padding-right:1.2rem; margin:0.5rem 0;">$1</ul>');

    // Citation markers [1] -> clickable refs (no reversing Arabic)
    html = html.replace(/\[(\d+)\]/g, (m, num) => {
      const cite = (citations || []).find(c => String(c.citation_id) === String(num));
      if (cite) {
        return `<a href="#" class="cite-ref" data-doc-id="${esc(cite.doc_id)}" data-chunk-id="${esc(cite.chunk_id)}" title="عرض المصدر ${num}">[${num}]</a>`;
      }
      return m;
    });

    html = html.split('\n\n').map(p => {
      p = p.trim();
      if (!p) return '';
      if (p.startsWith('<h') || p.startsWith('<ul') || p.startsWith('<ol') || p.startsWith('<table')) {
        return p;
      }
      return `<p>${p.replace(/\n/g, '<br>')}</p>`;
    }).join('');

    return html;
  }

  function bindCitationLinks(container, citations) {
    if (!container) return;
    container.querySelectorAll('.cite-ref').forEach(a => {
      a.addEventListener('click', (e) => {
        e.preventDefault();
        const docId = a.getAttribute('data-doc-id');
        const chunkId = a.getAttribute('data-chunk-id');
        if (docId && chunkId) openSourceViewer(docId, chunkId);
      });
    });
  }

  function renderAnswerMapCard(mapData, citations) {
    if (!mapData || !mapData.nodes || !mapData.edges) return null;

    const nodeById = {};
    (mapData.nodes || []).forEach(n => { nodeById[n.id] = n; });
    const rootId = mapData.rootId;
    const root = nodeById[rootId];
    if (!root) return null;

    const childEdges = (mapData.edges || []).filter(e => e.from === rootId);
    const wrap = document.createElement('div');
    wrap.className = 'answer-map-wrap';

    const toggleBtn = document.createElement('button');
    toggleBtn.type = 'button';
    toggleBtn.className = 'btn-show-answer-map';
    toggleBtn.innerHTML = `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
        <circle cx="12" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/>
        <path d="M12 7v4M12 11l-6 6M12 11l6 6"/>
      </svg>
      <span>عرض خريطة الإجابة</span>
    `;

    const card = document.createElement('div');
    card.className = 'answer-map-card hidden';
    card.setAttribute('dir', 'rtl');

    const header = document.createElement('div');
    header.className = 'answer-map-header';
    header.innerHTML = `
      <div class="answer-map-title">خريطة الإجابة</div>
      ${mapData.isDemo ? '<span class="answer-map-demo-badge">عينة توضيحية</span>' : ''}
    `;
    card.appendChild(header);

    const tree = document.createElement('div');
    tree.className = 'answer-map-tree';

    const rootEl = document.createElement('div');
    rootEl.className = 'am-root';
    rootEl.textContent = root.label;
    rootEl.tabIndex = 0;
    tree.appendChild(rootEl);

    const branches = document.createElement('div');
    branches.className = 'am-branches';

    const detailPanel = document.createElement('div');
    detailPanel.className = 'am-detail-panel hidden';

    function showNodeDetail(node) {
      if (!node) return;
      detailPanel.classList.remove('hidden');
      const sources = mapData.sources || [];
      let chips = '';
      (node.sourceIds || []).forEach(sid => {
        const src = sources.find(s => String(s.id) === String(sid));
        const cite = (citations || []).find(c => String(c.chunk_id) === String(sid) || String(c.citation_id) === String(sid));
        const label = cite ? `[${cite.citation_id}]` : (src ? src.title : sid);
        const docId = cite ? cite.doc_id : (src && src.doc_id) || '';
        const chunkId = cite ? cite.chunk_id : (src && src.chunk_id) || sid;
        chips += `<button type="button" class="am-source-chip" data-doc-id="${esc(docId)}" data-chunk-id="${esc(chunkId)}" data-demo-excerpt="${src && mapData.isDemo ? encodeURIComponent(src.excerpt || '') : ''}">${esc(label)}</button>`;
      });
      detailPanel.innerHTML = `
        <div class="am-detail-title">${esc(node.label)}</div>
        <div>${esc(node.detail || node.label)}</div>
        <div>${chips}</div>
      `;
      detailPanel.querySelectorAll('.am-source-chip').forEach(btn => {
        btn.addEventListener('click', () => {
          const demoEx = btn.getAttribute('data-demo-excerpt');
          const docId = btn.getAttribute('data-doc-id');
          const chunkId = btn.getAttribute('data-chunk-id');
          if (mapData.isDemo && demoEx) {
            sourceViewerTitle.textContent = 'مصدر تجريبي (عينة توضيحية)';
            sourceViewerSubtitle.textContent = node.label;
            sourceViewerMeta.innerHTML = '<span class="answer-map-demo-badge">عينة توضيحية</span>';
            sourceViewerContent.textContent = decodeURIComponent(demoEx);
            state.currentViewingSourceText = decodeURIComponent(demoEx);
            sourceViewerModal.classList.add('active');
            return;
          }
          if (docId && chunkId) openSourceViewer(docId, chunkId);
        });
      });
    }

    rootEl.addEventListener('click', () => showNodeDetail(root));

    childEdges.forEach(edge => {
      const branchNode = nodeById[edge.to];
      if (!branchNode) return;
      const branch = document.createElement('div');
      branch.className = 'am-branch';

      if (edge.label) {
        const elab = document.createElement('div');
        elab.className = 'am-edge-label';
        elab.textContent = edge.label;
        branch.appendChild(elab);
      }

      const mainNode = document.createElement('div');
      mainNode.className = 'am-node';
      mainNode.textContent = branchNode.label;
      mainNode.addEventListener('click', () => {
        branch.querySelectorAll('.am-node').forEach(n => n.classList.remove('active'));
        mainNode.classList.add('active');
        showNodeDetail(branchNode);
      });
      branch.appendChild(mainNode);

      const grandchildren = (mapData.edges || []).filter(e => e.from === branchNode.id);
      if (grandchildren.length) {
        const kids = document.createElement('div');
        kids.className = 'am-children';
        grandchildren.forEach(ge => {
          const gn = nodeById[ge.to];
          if (!gn) return;
          if (ge.label) {
            const gel = document.createElement('div');
            gel.className = 'am-child-edge';
            gel.textContent = ge.label;
            kids.appendChild(gel);
          }
          const child = document.createElement('div');
          child.className = 'am-node';
          child.textContent = gn.label;
          child.addEventListener('click', () => {
            branch.querySelectorAll('.am-node').forEach(n => n.classList.remove('active'));
            child.classList.add('active');
            showNodeDetail(gn);
          });
          kids.appendChild(child);
        });
        branch.appendChild(kids);

        const collapseBtn = document.createElement('button');
        collapseBtn.type = 'button';
        collapseBtn.className = 'am-collapse-toggle';
        collapseBtn.textContent = 'طي التفاصيل';
        collapseBtn.addEventListener('click', () => {
          branch.classList.toggle('collapsed');
          collapseBtn.textContent = branch.classList.contains('collapsed') ? 'عرض التفاصيل' : 'طي التفاصيل';
        });
        branch.appendChild(collapseBtn);
      }

      branches.appendChild(branch);
    });

    tree.appendChild(branches);
    card.appendChild(tree);
    card.appendChild(detailPanel);

    toggleBtn.addEventListener('click', () => {
      const opening = card.classList.contains('hidden');
      card.classList.toggle('hidden');
      toggleBtn.querySelector('span').textContent = opening ? 'إخفاء خريطة الإجابة' : 'عرض خريطة الإجابة';
    });

    wrap.appendChild(toggleBtn);
    wrap.appendChild(card);
    return wrap;
  }

  // ==========================================
  // Chat Message & Citations Rendering
  // ==========================================
  // Reading starts at the question, not at the end of the answer
  function keepQuestionInView() {
    if (!state.questionRow || !state.questionRow.isConnected) {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
      return;
    }
    const offset = state.questionRow.getBoundingClientRect().top
      - messagesContainer.getBoundingClientRect().top;
    messagesContainer.scrollTop += offset - 12;
  }

  // The hero collapses when chatting starts, which moves the page under the reader
  function focusChat() {
    const chat = document.getElementById('chat');
    const align = () => {
      // Instant: the page's smooth scrolling would be cut off by the layout change
      window.scrollTo({ top: window.scrollY + chat.getBoundingClientRect().top, behavior: 'instant' });
      keepQuestionInView();
    };
    align();
    setTimeout(align, 450);
  }

  function appendMessage(role, initialText = '') {
    if (emptyState) emptyState.style.display = 'none';

    const row = document.createElement('div');
    row.className = `message-row ${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.innerHTML = formatMarkdown(initialText);

    row.appendChild(bubble);
    messagesContainer.appendChild(row);
    keepQuestionInView();

    return { row, bubble };
  }

  function appendCitationsCards(bubbleElement, citations) {
    if (!citations || citations.length === 0) return;

    const container = document.createElement('div');
    container.className = 'sources-container';

    const title = document.createElement('div');
    title.className = 'sources-title';
    title.innerHTML = `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
      </svg>
      <span>الأدلة المعتمدة المستند إليها (${citations.length}):</span>
    `;
    container.appendChild(title);

    const grid = document.createElement('div');
    grid.className = 'sources-grid';

    citations.forEach(c => {
      const card = document.createElement('div');
      card.className = 'source-card';

      const pageBadge = c.page ? `<span class="source-page-badge">صفحة ${esc(c.page)}</span>` : '';

      card.innerHTML = `
        <div>
          <div class="source-card-header">
            <span class="source-card-name" title="${esc(c.doc_title)}">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#FF6B35" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
              ${esc(c.doc_title)}
            </span>
            ${pageBadge}
          </div>
          <div style="font-size:0.75rem; font-weight:700; color:#0284C7; margin:0.2rem 0;">📌 ${esc(c.section_title)}</div>
          <p class="source-excerpt" title="${esc(c.excerpt)}">«${esc(c.excerpt)}»</p>
        </div>
        <button type="button" class="btn-primary-orange btn-view-source" data-doc-id="${esc(c.doc_id)}" data-chunk-id="${esc(c.chunk_id)}" style="padding:0.35rem 0.85rem; font-size:0.78rem; min-height:32px; border-radius:8px; align-self:flex-start; margin-top:0.35rem;">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
          <span>عرض المصدر</span>
        </button>
      `;
      grid.appendChild(card);
    });

    container.appendChild(grid);
    bubbleElement.appendChild(container);

    // Attach in-app viewer handlers
    container.querySelectorAll('.btn-view-source').forEach(btn => {
      btn.addEventListener('click', () => {
        const docId = btn.getAttribute('data-doc-id');
        const chunkId = btn.getAttribute('data-chunk-id');
        openSourceViewer(docId, chunkId);
      });
    });

    keepQuestionInView();
  }

  function addMessageFooter(bubbleElement, rawText) {
    const footer = document.createElement('div');
    footer.className = 'message-footer';

    const copyBtn = document.createElement('button');
    copyBtn.type = 'button';
    copyBtn.className = 'btn-icon-sm';
    copyBtn.innerHTML = `
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
      <span>نسخ الإجابة</span>
    `;

    copyBtn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(rawText);
        showToast('تم نسخ الإجابة بنجاح');
        copyBtn.querySelector('span').textContent = 'تم النسخ!';
        setTimeout(() => copyBtn.querySelector('span').textContent = 'نسخ الإجابة', 2000);
      } catch (e) {
        showToast('تعذر النسخ');
      }
    });

    footer.appendChild(copyBtn);
    bubbleElement.appendChild(footer);
  }

  // ==========================================
  // In-App Source Viewer Modal
  // ==========================================
  async function openSourceViewer(docId, chunkId) {
    try {
      showToast('جاري استرجاع نص المصدر المعتمد...');
      const res = await fetch(`/api/source/${encodeURIComponent(docId)}/${encodeURIComponent(chunkId)}`);
      if (!res.ok) throw new Error('المصدر غير متاح أو لا يملك صلاحية العرض');
      const data = await res.json();
      const src = data.source;

      sourceViewerTitle.textContent = src.doc_title;
      sourceViewerSubtitle.textContent = `القسم: ${src.section_title}`;
      
      const pageInfo = src.page ? `<span>📄 <strong>الصفحة:</strong> ${esc(src.page)}</span>` : '';
      const dateInfo = src.release_date ? `<span>📅 <strong>تاريخ الإصدار:</strong> ${esc(src.release_date)}</span>` : '';
      const fileInfo = src.original_filename ? `<span>📁 <strong>الملف الأصلي:</strong> ${esc(src.original_filename)}</span>` : '';

      sourceViewerMeta.innerHTML = `${pageInfo} ${dateInfo} ${fileInfo}`;
      sourceViewerContent.innerHTML = formatMarkdown(src.content);
      state.currentViewingSourceText = src.content;

      sourceViewerModal.classList.add('active');
    } catch (e) {
      showToast(`خطأ: ${e.message}`);
    }
  }

  closeSourceViewerBtn.addEventListener('click', () => {
    sourceViewerModal.classList.remove('active');
  });

  copySourceTextBtn.addEventListener('click', async () => {
    if (state.currentViewingSourceText) {
      await navigator.clipboard.writeText(state.currentViewingSourceText);
      showToast('تم نسخ نص المصدر كاملاً');
    }
  });

  // ==========================================
  // Chat Submit & Streaming
  // ==========================================
  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = queryInput.value.trim();
    if (!query || state.isGenerating) return;

    collapseHero();

    state.questionRow = appendMessage('user', query).row;
    state.chatHistory.push({ role: 'user', content: query });
    queryInput.value = '';
    queryInput.style.height = 'auto';

    state.isGenerating = true;
    sendBtn.disabled = true;
    stopGenerationBtn.classList.add('visible');
    thinkingIndicator.style.display = 'flex';
    keepQuestionInView();

    const { bubble: assistantBubble } = appendMessage('assistant', '');
    focusChat();
    let accumulatedText = '';
    let receivedCitations = [];
    let receivedAnswerMap = null;
    let streamFailed = false;

    state.abortController = new AbortController();

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          // The current question is sent as `query`, so it is not repeated here
          history: state.chatHistory.slice(-7, -1).map(m => ({ role: m.role, content: m.content.slice(0, 4000) }))
        }),
        signal: state.abortController.signal
      });

      if (!response.ok) {
        throw new Error(`خطأ في استجابة الخادم: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            const rawJson = trimmed.slice(6);
            try {
              const data = JSON.parse(rawJson);

              if (data.error) {
                streamFailed = true;
                accumulatedText = `⚠️ **تنبيه:** ${data.error}`;
                assistantBubble.innerHTML = formatMarkdown(accumulatedText, []);
              } else if (data.text) {
                accumulatedText += data.text;
                assistantBubble.innerHTML = formatMarkdown(accumulatedText, receivedCitations);
                thinkingIndicator.style.display = 'none';
                keepQuestionInView();
              } else if (data.done) {
                receivedCitations = data.citations || [];
                receivedAnswerMap = data.answer_map || null;
              }
            } catch (err) {}
          }
        }
      }

      if (!streamFailed && !accumulatedText.trim()) {
        accumulatedText = '⚠️ تعذر إتمام الإجابة من النموذج.';
        streamFailed = true;
      }

      assistantBubble.innerHTML = formatMarkdown(accumulatedText, receivedCitations);
      bindCitationLinks(assistantBubble, receivedCitations);

      if (!streamFailed) {
        state.chatHistory.push({ role: 'assistant', content: accumulatedText });
        appendCitationsCards(assistantBubble, receivedCitations);
        const mapEl = renderAnswerMapCard(receivedAnswerMap, receivedCitations);
        if (mapEl) assistantBubble.appendChild(mapEl);
        addMessageFooter(assistantBubble, accumulatedText);
      }

    } catch (err) {
      if (err.name === 'AbortError') {
        accumulatedText += '\n\n*(تم إيقاف الاستجابة من قبل المستخدم)*';
        assistantBubble.innerHTML = formatMarkdown(accumulatedText, receivedCitations);
        showToast('تم إيقاف الاستجابة');
      } else {
        assistantBubble.innerHTML = formatMarkdown(
          '⚠️ **تعذر إتمام الإجابة.** يرجى إعادة المحاولة، وإن تكررت المشكلة فراجع إعداد مفتاح Gemini.',
          []
        );
      }
    } finally {
      state.isGenerating = false;
      state.abortController = null;
      sendBtn.disabled = false;
      stopGenerationBtn.classList.remove('visible');
      thinkingIndicator.style.display = 'none';
      keepQuestionInView();
    }
  });

  stopGenerationBtn.addEventListener('click', () => {
    if (state.abortController) state.abortController.abort();
  });

  newChatBtn.addEventListener('click', () => {
    if (state.isGenerating && state.abortController) state.abortController.abort();
    state.chatHistory = [];
    state.questionRow = null;
    messagesContainer.innerHTML = '';
    if (emptyState) {
      messagesContainer.appendChild(emptyState);
      emptyState.style.display = 'flex';
    }
    heroSection.classList.remove('collapsed');
    compactBanner.classList.remove('visible');
    state.hasSentFirstMessage = false;
    showToast('تم بدء محادثة جديدة');
  });

  // ==========================================
  // إضافة مفتاح الذكاء — إرشادات فقط
  // ==========================================
  function updateKeyStatusHint() {
    const hint = document.getElementById('geminiKeyStatusHint');
    if (!hint) return;
    const ready = state.systemStatus && state.systemStatus.has_gemini_key;
    hint.textContent = ready
      ? 'الحالة: مفتاح مهيأ على الخادم (القيمة غير معروضة ولا يمكن استرجاعها من الواجهة).'
      : 'الحالة: الإعداد غير مكتمل — لم يُعثر على GEMINI_API_KEY في بيئة الخادم.';
  }

  if (adminTriggerBtn && adminModal) {
    adminTriggerBtn.addEventListener('click', () => {
      updateKeyStatusHint();
      adminModal.classList.add('active');
    });
  }
  if (closeAdminModalBtn && adminModal) {
    closeAdminModalBtn.addEventListener('click', () => {
      adminModal.classList.remove('active');
    });
  }

  // Initial load
  fetchBranding();
  fetchStatus().then(() => updateKeyStatusHint());
  fetchSources();
});
