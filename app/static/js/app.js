/**
 * Indic Tender Platform - Interactive Frontend Controller
 * Central Public Procurement Portal (CPPP) Data Hub
 */

const state = {
  query: '',
  category: 'ALL',
  ministry: 'ALL',
  status: 'ALL',
  page: 1,
  limit: 12,
  sortBy: 'bid_submission_closing_date',
  sortOrder: 'asc',
  view: 'grid', // 'grid' or 'table'
  totalItems: 0,
  totalPages: 1
};

// DOM Cache
const dom = {
  statsTotal: document.getElementById('statTotalTenders'),
  statsActive: document.getElementById('statActiveTenders'),
  statsValue: document.getElementById('statTotalValue'),
  statsClosing: document.getElementById('statClosingSoon'),
  latestSyncTime: document.getElementById('latestSyncTime'),
  
  searchInput: document.getElementById('searchInput'),
  clearSearchBtn: document.getElementById('clearSearchBtn'),
  ministryFilter: document.getElementById('ministryFilter'),
  statusFilter: document.getElementById('statusFilter'),
  sortSelect: document.getElementById('sortSelect'),
  categoryPills: document.getElementById('categoryPills'),
  
  syncBtn: document.getElementById('syncBtn'),
  syncModeSelect: document.getElementById('syncModeSelect'),
  syncStatusBanner: document.getElementById('syncStatusBanner'),
  viewRunsBtn: document.getElementById('viewRunsBtn'),
  exportCsvBtn: document.getElementById('exportCsvBtn'),
  
  gridBtn: document.getElementById('gridBtn'),
  tableBtn: document.getElementById('tableBtn'),
  tenderGrid: document.getElementById('tenderGrid'),
  tenderTableWrap: document.getElementById('tenderTableWrap'),
  tenderTableBody: document.getElementById('tenderTableBody'),
  
  resultsCount: document.getElementById('resultsCount'),
  paginationBar: document.getElementById('paginationBar'),
  
  // Modals
  detailModal: document.getElementById('detailModal'),
  detailModalClose: document.getElementById('detailModalClose'),
  detailModalContent: document.getElementById('detailModalContent'),
  
  runsModal: document.getElementById('runsModal'),
  runsModalClose: document.getElementById('runsModalClose'),
  runsModalBody: document.getElementById('runsModalBody'),
  
  toastContainer: document.getElementById('toastContainer'),
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  loadInitialData();
});

function setupEventListeners() {
  // Search input with debounce
  let debounceTimer;
  dom.searchInput.addEventListener('input', (e) => {
    state.query = e.target.value.trim();
    dom.clearSearchBtn.style.display = state.query ? 'block' : 'none';
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      state.page = 1;
      fetchTenders();
    }, 300);
  });

  dom.clearSearchBtn.addEventListener('click', () => {
    dom.searchInput.value = '';
    state.query = '';
    dom.clearSearchBtn.style.display = 'none';
    state.page = 1;
    fetchTenders();
  });

  // Ministry & Status dropdowns
  dom.ministryFilter.addEventListener('change', (e) => {
    state.ministry = e.target.value;
    state.page = 1;
    fetchTenders();
  });

  dom.statusFilter.addEventListener('change', (e) => {
    state.status = e.target.value;
    state.page = 1;
    fetchTenders();
  });

  // Sort select
  dom.sortSelect.addEventListener('change', (e) => {
    const val = e.target.value;
    if (val === 'closing_asc') {
      state.sortBy = 'bid_submission_closing_date';
      state.sortOrder = 'asc';
    } else if (val === 'closing_desc') {
      state.sortBy = 'bid_submission_closing_date';
      state.sortOrder = 'desc';
    } else if (val === 'value_desc') {
      state.sortBy = 'tender_value_inr';
      state.sortOrder = 'desc';
    } else if (val === 'updated_desc') {
      state.sortBy = 'last_updated_at';
      state.sortOrder = 'desc';
    }
    state.page = 1;
    fetchTenders();
  });

  // Category Pills
  dom.categoryPills.addEventListener('click', (e) => {
    const pill = e.target.closest('.category-pill');
    if (!pill) return;
    document.querySelectorAll('.category-pill').forEach(p => p.classList.remove('active'));
    pill.classList.add('active');
    state.category = pill.dataset.category;
    state.page = 1;
    fetchTenders();
  });

  // View switchers
  dom.gridBtn.addEventListener('click', () => switchView('grid'));
  dom.tableBtn.addEventListener('click', () => switchView('table'));

  // Ingestion trigger
  dom.syncBtn.addEventListener('click', () => triggerSync());
  dom.viewRunsBtn.addEventListener('click', () => openRunsModal());
  dom.exportCsvBtn.addEventListener('click', () => exportData());

  // Modal Closers
  dom.detailModalClose.addEventListener('click', () => dom.detailModal.classList.remove('open'));
  dom.detailModal.addEventListener('click', (e) => {
    if (e.target === dom.detailModal) dom.detailModal.classList.remove('open');
  });

  dom.runsModalClose.addEventListener('click', () => dom.runsModal.classList.remove('open'));
  dom.runsModal.addEventListener('click', (e) => {
    if (e.target === dom.runsModal) dom.runsModal.classList.remove('open');
  });
}

function switchView(viewName) {
  state.view = viewName;
  if (viewName === 'grid') {
    dom.gridBtn.classList.add('active');
    dom.tableBtn.classList.remove('active');
    dom.tenderGrid.style.display = 'grid';
    dom.tenderTableWrap.style.display = 'none';
  } else {
    dom.gridBtn.classList.remove('active');
    dom.tableBtn.classList.add('active');
    dom.tenderGrid.style.display = 'none';
    dom.tenderTableWrap.style.display = 'block';
  }
}

async function loadInitialData() {
  await Promise.all([
    fetchStats(),
    fetchFilterOptions(),
    fetchTenders()
  ]);
}

// Fetch Platform Analytics Stats
async function fetchStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) throw new Error('Stats fetch error');
    const data = await res.json();
    
    dom.statsTotal.innerText = data.total_tenders.toLocaleString('en-IN');
    dom.statsActive.innerText = data.active_tenders.toLocaleString('en-IN');
    dom.statsValue.innerText = `₹ ${data.total_portfolio_value_cr} Cr`;
    dom.statsClosing.innerText = data.closing_soon_tenders.toLocaleString('en-IN');

    if (data.latest_sync_time) {
      const syncDate = new Date(data.latest_sync_time);
      dom.latestSyncTime.innerText = `Last CPPP Sync: ${syncDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`;
    }
  } catch (err) {
    console.error('Failed to load stats:', err);
  }
}

// Fetch Filter Dropdown Options
async function fetchFilterOptions() {
  try {
    const res = await fetch('/api/filter-options');
    if (!res.ok) throw new Error('Filter options error');
    const data = await res.json();

    // Populate Ministries
    dom.ministryFilter.innerHTML = '<option value="ALL">All Ministries & Authorities</option>';
    data.ministries.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m;
      opt.innerText = m;
      dom.ministryFilter.appendChild(opt);
    });
  } catch (err) {
    console.error('Failed to load filter options:', err);
  }
}

// Fetch Tender Listing
async function fetchTenders() {
  const params = new URLSearchParams();
  if (state.query) params.append('query', state.query);
  if (state.category && state.category !== 'ALL') params.append('category', state.category);
  if (state.ministry && state.ministry !== 'ALL') params.append('ministry', state.ministry);
  if (state.status && state.status !== 'ALL') params.append('status', state.status);
  params.append('page', state.page);
  params.append('limit', state.limit);
  params.append('sort_by', state.sortBy);
  params.append('sort_order', state.sortOrder);

  try {
    const res = await fetch(`/api/tenders?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch tenders');
    const data = await res.json();

    state.totalItems = data.total;
    state.totalPages = data.total_pages;

    dom.resultsCount.innerHTML = `Showing <strong>${data.items.length}</strong> of <strong>${data.total}</strong> active CPPP listings`;

    renderGridView(data.items);
    renderTableView(data.items);
    renderPagination();
  } catch (err) {
    console.error('Failed to query tenders:', err);
    showToast('Failed to load tenders. Please retry.', 'error');
  }
}

// Render Grid Cards
function renderGridView(items) {
  if (items.length === 0) {
    dom.tenderGrid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 4rem 1rem; color: var(--text-dim);">
        <p style="font-size: 1.1rem; margin-bottom: 0.5rem;">No procurement listings match your filter criteria.</p>
        <p style="font-size: 0.85rem;">Try modifying search terms or resetting filters.</p>
      </div>
    `;
    return;
  }

  dom.tenderGrid.innerHTML = items.map(t => {
    const daysLeft = formatClosingDays(t.bid_submission_closing_date);
    const urgentClass = daysLeft.isUrgent ? 'urgent' : '';

    return `
      <div class="tender-card" onclick="openDetailModal('${t.id}')">
        <div>
          <div class="card-top">
            <span class="org-chain-badge" title="${escapeHtml(t.organisation_chain)}">
              ${escapeHtml(t.department || t.ministry_or_state)}
            </span>
            <span class="status-chip ${t.status}">
              ${formatStatusLabel(t.status)}
            </span>
          </div>

          <h3 class="card-title" title="${escapeHtml(t.title)}">${escapeHtml(t.title)}</h3>

          <div class="meta-identifiers">
            <span>Ref: <strong>${escapeHtml(t.tender_reference_number)}</strong></span>
            <span>ID: <strong>${escapeHtml(t.source_tender_id)}</strong></span>
          </div>

          <div class="card-metrics">
            <div class="metric-block">
              <div class="metric-lbl">Tender Value</div>
              <div class="metric-val value-highlight">${t.tender_value_display || 'Not Disclosed'}</div>
            </div>
            <div class="metric-block">
              <div class="metric-lbl">Category</div>
              <div class="metric-val">${escapeHtml(t.tender_category)}</div>
            </div>
          </div>
        </div>

        <div class="card-footer">
          <div class="closing-pill ${urgentClass}">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            <span>${daysLeft.text}</span>
          </div>
          <div style="display:flex; align-items:center; gap:0.4rem;">
            ${t.corrigenda_count > 0 ? `<span class="version-pill" style="color:var(--accent-purple); border-color:var(--accent-purple);">Corrigenda: ${t.corrigenda_count}</span>` : ''}
            <span class="version-pill">v${t.version}</span>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// Render Table Rows
function renderTableView(items) {
  if (items.length === 0) {
    dom.tenderTableBody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2rem;">No listings found.</td></tr>`;
    return;
  }

  dom.tenderTableBody.innerHTML = items.map(t => {
    const daysLeft = formatClosingDays(t.bid_submission_closing_date);
    return `
      <tr onclick="openDetailModal('${t.id}')">
        <td style="font-weight: 600; color: #60a5fa;">${escapeHtml(t.source_tender_id)}</td>
        <td style="max-width: 320px;">
          <div style="font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(t.title)}</div>
          <div style="font-size:0.75rem; color:var(--text-dim);">${escapeHtml(t.tender_reference_number)}</div>
        </td>
        <td style="max-width: 200px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${escapeHtml(t.organisation_chain)}">
          ${escapeHtml(t.ministry_or_state)}
        </td>
        <td><span class="version-pill">${escapeHtml(t.tender_category)}</span></td>
        <td style="font-weight:700; color:#93c5fd;">${t.tender_value_display || 'Not Disclosed'}</td>
        <td>
          <div style="font-weight:600;">${formatDate(t.bid_submission_closing_date)}</div>
          <div style="font-size:0.75rem; color:var(--text-dim);">${daysLeft.text}</div>
        </td>
        <td><span class="status-chip ${t.status}">${formatStatusLabel(t.status)}</span></td>
      </tr>
    `;
  }).join('');
}

// Render Pagination Controls
function renderPagination() {
  if (state.totalPages <= 1) {
    dom.paginationBar.innerHTML = '';
    return;
  }

  let html = `
    <button class="page-btn" ${state.page === 1 ? 'disabled' : ''} onclick="changePage(${state.page - 1})">
      &larr; Prev
    </button>
  `;

  for (let i = 1; i <= state.totalPages; i++) {
    html += `
      <button class="page-btn ${state.page === i ? 'active' : ''}" onclick="changePage(${i})">
        ${i}
      </button>
    `;
  }

  html += `
    <button class="page-btn ${state.page === state.totalPages ? 'disabled' : ''} onclick="changePage(${state.page + 1})">
      Next &rarr;
    </button>
  `;

  dom.paginationBar.innerHTML = html;
}

window.changePage = function(p) {
  if (p < 1 || p > state.totalPages) return;
  state.page = p;
  fetchTenders();
  window.scrollTo({ top: 350, behavior: 'smooth' });
};

// Open Single Tender Detail Modal
window.openDetailModal = async function(id) {
  try {
    const res = await fetch(`/api/tenders/${id}`);
    if (!res.ok) throw new Error('Failed to load tender details');
    const t = await res.json();

    const daysLeft = formatClosingDays(t.bid_submission_closing_date);

    dom.detailModalContent.innerHTML = `
      <div class="modal-header">
        <div>
          <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.5rem;">
            <span class="status-chip ${t.status}">${formatStatusLabel(t.status)}</span>
            <span class="version-pill">Version ${t.version}</span>
            <span class="version-pill" style="color:var(--accent-blue-light);">Source: ${t.source}</span>
          </div>
          <h2>${escapeHtml(t.title)}</h2>
          <div style="font-size:0.8rem; color:var(--text-dim); margin-top:0.35rem;">
            Tender ID: <strong style="color:var(--text-muted);">${escapeHtml(t.source_tender_id)}</strong> | 
            Ref: <strong style="color:var(--text-muted);">${escapeHtml(t.tender_reference_number)}</strong>
          </div>
        </div>
      </div>

      <div class="modal-body">
        <!-- Section 1: Organisation Hierarchy -->
        <div class="detail-section">
          <div class="section-title">
            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path></svg>
            Procuring Authority Hierarchy
          </div>
          <div style="background:var(--bg-surface); padding:1rem; border-radius:var(--radius-md); border:1px solid var(--border-subtle); font-size:0.85rem;">
            ${escapeHtml(t.organisation_chain).split('||').map((part, i) => `
              <div style="padding: 4px 0; display:flex; align-items:center; gap:0.5rem;">
                <span style="color:var(--text-dim);">${'—'.repeat(i + 1)}</span>
                <span style="font-weight:${i === 0 ? '700' : '500'}; color:${i === 0 ? 'var(--accent-blue-light)' : 'var(--text-main)'};">
                  ${escapeHtml(part.trim())}
                </span>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- Section 2: Financial Details -->
        <div class="detail-section">
          <div class="section-title">
            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            Financial Classification & Fees
          </div>
          <div class="detail-grid">
            <div class="detail-item">
              <div class="item-label">Tender Estimated Value</div>
              <div class="item-val" style="color:#60a5fa; font-size:1.15rem;">${t.tender_value_display || 'Not Disclosed'}</div>
            </div>
            <div class="detail-item">
              <div class="item-label">Earnest Money Deposit (EMD)</div>
              <div class="item-val">${t.emd_amount_inr ? `₹ ${t.emd_amount_inr.toLocaleString('en-IN')}` : 'Exempted / Nil'}</div>
            </div>
            <div class="detail-item">
              <div class="item-label">Tender Category</div>
              <div class="item-val">${escapeHtml(t.tender_category)}</div>
            </div>
            <div class="detail-item">
              <div class="item-label">Product / Sub-Category</div>
              <div class="item-val">${escapeHtml(t.product_category || 'General')}</div>
            </div>
          </div>
        </div>

        <!-- Section 3: Critical Dates Timeline -->
        <div class="detail-section">
          <div class="section-title">
            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
            Critical Procurement Milestones
          </div>
          <div class="timeline">
            <div class="timeline-step">
              <div class="step-name">Published Date</div>
              <div class="step-date">${formatDate(t.tender_published_date)}</div>
            </div>
            <div class="timeline-step">
              <div class="step-name">Bid Submission Starts</div>
              <div class="step-date">${formatDate(t.bid_submission_start_date)}</div>
            </div>
            <div class="timeline-step">
              <div class="step-name">Closing Deadline</div>
              <div class="step-date" style="color:var(--accent-amber);">${formatDate(t.bid_submission_closing_date)}</div>
              <div style="font-size:0.75rem; color:var(--text-dim);">${daysLeft.text}</div>
            </div>
            <div class="timeline-step">
              <div class="step-name">Bid Opening Date</div>
              <div class="step-date">${formatDate(t.bid_opening_date)}</div>
            </div>
          </div>
        </div>

        <!-- Section 4: Location & Corrigenda -->
        <div class="detail-section">
          <div class="section-title">
            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path></svg>
            Execution Location & Amendments
          </div>
          <div class="detail-grid">
            <div class="detail-item">
              <div class="item-label">Location / Site</div>
              <div class="item-val">${escapeHtml(t.location || 'Not Specified')}</div>
            </div>
            <div class="detail-item">
              <div class="item-label">Postal Pincode</div>
              <div class="item-val">${escapeHtml(t.pincode || 'N/A')}</div>
            </div>
            <div class="detail-item">
              <div class="item-label">Corrigenda Published</div>
              <div class="item-val">${t.corrigenda_count > 0 ? `<span style="color:var(--accent-purple); font-weight:700;">${t.corrigenda_count} Amendments</span>` : 'Nil'}</div>
            </div>
            <div class="detail-item">
              <div class="item-label">Content SHA-256 Fingerprint</div>
              <div class="item-val" style="font-family:monospace; font-size:0.7rem; color:var(--text-dim);" title="${t.content_hash}">
                ${t.content_hash ? t.content_hash.substring(0, 16) + '...' : 'N/A'}
              </div>
            </div>
          </div>
        </div>

        <!-- Section 5: Version History Audit Trail -->
        ${t.history && t.history.length > 0 ? `
          <div class="detail-section">
            <div class="section-title">
              <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
              Deduplication Audit Trail (${t.history.length} Revisions)
            </div>
            ${t.history.map(h => `
              <div class="history-entry">
                <div class="history-meta">
                  <strong>Revision v${h.version}</strong>
                  <span>${formatDate(h.changed_at)}</span>
                </div>
                <div style="font-size:0.8rem; color:var(--text-muted);">
                  ${escapeHtml(h.reason || 'Field modification recorded')}
                </div>
                ${h.changes ? `
                  <div style="margin-top:0.4rem; font-size:0.75rem; font-family:monospace; color:#93c5fd;">
                    ${Object.entries(h.changes).map(([f, diff]) => `
                      <div>&bull; <strong>${f}</strong>: "${diff.previous}" &rarr; "${diff.new}"</div>
                    `).join('')}
                  </div>
                ` : ''}
              </div>
            `).join('')}
          </div>
        ` : ''}

        <!-- Section 6: Action Buttons -->
        <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:1rem; margin-top:2rem; padding-top:1.25rem; border-top:1px solid var(--border-subtle);">
          <div style="display:flex; gap:0.5rem;">
            <button class="btn btn-secondary" onclick="copyToClipboard('${escapeHtml(t.source_tender_id)}')">
              Copy Tender ID
            </button>
            <button class="btn btn-outline" onclick="toggleJsonView()">
              Toggle JSON View
            </button>
          </div>
          <a href="${t.source_url}" target="_blank" rel="noopener noreferrer" class="btn btn-primary">
            <span>Open CPPP Portal Listing</span>
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
          </a>
        </div>

        <!-- Raw JSON Viewer -->
        <div id="jsonViewerBlock" style="display:none; margin-top:1.5rem;">
          <pre class="json-box">${JSON.stringify(t, null, 2)}</pre>
        </div>
      </div>
    `;

    dom.detailModal.classList.add('open');
  } catch (err) {
    console.error('Failed to open modal:', err);
    showToast('Failed to load tender details', 'error');
  }
};

window.toggleJsonView = function() {
  const el = document.getElementById('jsonViewerBlock');
  if (el) {
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
  }
};

// Trigger Ingestion Sync
async function triggerSync() {
  const mode = dom.syncModeSelect.value;
  dom.syncBtn.disabled = true;
  dom.syncBtn.innerHTML = `
    <svg class="animate-spin" width="16" height="16" fill="none" viewBox="0 0 24 24" style="animation: spin 1s linear infinite;"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" style="opacity:0.25;"></circle><path fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" style="opacity:0.75;"></path></svg>
    Extracting...
  `;

  try {
    const res = await fetch('/api/ingest/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode })
    });
    const result = await res.json();

    if (result.run && result.run.status === 'COMPLETED') {
      showToast(
        `Sync Finished! Created: ${result.run.items_created}, Updated: ${result.run.items_updated}, Unchanged: ${result.run.items_unmodified}`,
        'success'
      );
    } else {
      showToast(`Ingestion finished with notes: ${result.message}`, 'info');
    }

    await fetchStats();
    await fetchFilterOptions();
    await fetchTenders();
  } catch (err) {
    console.error('Sync failed:', err);
    showToast('Ingestion encountered an error', 'error');
  } finally {
    dom.syncBtn.disabled = false;
    dom.syncBtn.innerHTML = `
      <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
      Sync CPPP Now
    `;
  }
}

// Ingestion Runs History Modal
async function openRunsModal() {
  try {
    const res = await fetch('/api/ingest/runs?limit=10');
    const runs = await res.json();

    dom.runsModalBody.innerHTML = runs.map(r => `
      <div style="background:var(--bg-surface); border:1px solid var(--border-subtle); border-radius:var(--radius-md); padding:1rem; margin-bottom:1rem;">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:0.5rem;">
          <div style="display:flex; align-items:center; gap:0.5rem;">
            <span class="status-chip ${r.status === 'COMPLETED' ? 'ACTIVE' : 'CLOSING_SOON'}">${r.status}</span>
            <strong style="font-family:monospace; font-size:0.85rem;">${r.run_id}</strong>
            <span class="version-pill">Mode: ${r.mode}</span>
          </div>
          <span style="font-size:0.75rem; color:var(--text-dim);">${formatDate(r.started_at)}</span>
        </div>
        
        <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:0.5rem; background:rgba(0,0,0,0.2); padding:0.6rem; border-radius:var(--radius-sm); font-size:0.8rem; margin:0.5rem 0;">
          <div>Extracted: <strong>${r.items_extracted}</strong></div>
          <div style="color:#34d399;">Created: <strong>${r.items_created}</strong></div>
          <div style="color:#60a5fa;">Updated: <strong>${r.items_updated}</strong></div>
          <div style="color:var(--text-muted);">Unmodified: <strong>${r.items_unmodified}</strong></div>
        </div>

        ${r.duration_ms ? `<div style="font-size:0.75rem; color:var(--text-dim);">Execution duration: ${r.duration_ms} ms</div>` : ''}

        ${r.logs && r.logs.length > 0 ? `
          <details style="margin-top:0.5rem; font-size:0.75rem;">
            <summary style="cursor:pointer; color:var(--accent-blue-light);">View Execution Logs (${r.logs.length} lines)</summary>
            <div style="background:#000; padding:0.5rem; border-radius:var(--radius-sm); max-height:160px; overflow-y:auto; font-family:monospace; color:#38bdf8; margin-top:0.4rem;">
              ${r.logs.map(l => `<div>${escapeHtml(l)}</div>`).join('')}
            </div>
          </details>
        ` : ''}
      </div>
    `).join('');

    dom.runsModal.classList.add('open');
  } catch (err) {
    showToast('Failed to fetch ingestion runs', 'error');
  }
}

// Export CSV
function exportData() {
  const params = new URLSearchParams();
  if (state.query) params.append('query', state.query);
  if (state.category && state.category !== 'ALL') params.append('category', state.category);
  if (state.ministry && state.ministry !== 'ALL') params.append('ministry', state.ministry);
  if (state.status && state.status !== 'ALL') params.append('status', state.status);
  
  window.location.href = `/api/export?${params.toString()}`;
  showToast('Preparing CSV download...', 'info');
}

// Utility Helpers
function formatDate(dateStr) {
  if (!dateStr) return 'N/A';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function formatClosingDays(dateStr) {
  if (!dateStr) return { text: 'No closing date', isUrgent: false };
  const closing = new Date(dateStr);
  const now = new Date();
  const diffMs = closing - now;
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays < 0) return { text: 'Bidding Closed', isUrgent: false };
  if (diffDays === 0) return { text: 'Closing Today!', isUrgent: true };
  if (diffDays === 1) return { text: '1 day left', isUrgent: true };
  if (diffDays <= 7) return { text: `${diffDays} days left`, isUrgent: true };
  return { text: `${diffDays} days left`, isUrgent: false };
}

function formatStatusLabel(st) {
  switch (st) {
    case 'ACTIVE': return 'Active';
    case 'CLOSING_SOON': return 'Closing Soon';
    case 'CORRIGENDUM_ISSUED': return 'Corrigendum';
    case 'CLOSED': return 'Closed';
    default: return st;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

window.copyToClipboard = function(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast(`Copied "${text}" to clipboard`, 'success');
  }).catch(() => {
    showToast('Failed to copy to clipboard', 'error');
  });
};

function showToast(msg, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerText = msg;
  dom.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
