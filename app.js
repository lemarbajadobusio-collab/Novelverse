// ── STATE ─────────────────────────────────────────────────────────
const API = '';  // same-origin
let supabaseClient = null;
let currentUser = null;
let currentNovelId = null;
let currentChapter = 1;
let currentGenre = '';
let searchTimer = null;
let currentTheme = 'dark';
let readerFontSize = 19;
let pendingDeleteAction = null;

// ── INIT ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  initReaderFontSize();
  await initSupabase();
  await checkAuth();
  loadNovels();
});

function initTheme() {
  const savedTheme = localStorage.getItem('novelverse-theme');
  const prefersLight = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches;
  currentTheme = savedTheme || (prefersLight ? 'light' : 'dark');
  applyTheme(currentTheme);
}

function applyTheme(theme) {
  currentTheme = theme === 'light' ? 'light' : 'dark';
  document.documentElement.dataset.theme = currentTheme;

  const btn = document.getElementById('themeToggle');
  if (btn) {
    const isLight = currentTheme === 'light';
    btn.textContent = isLight ? '☀' : '☾';
    btn.setAttribute('aria-label', `Switch to ${isLight ? 'dark' : 'light'} mode`);
    btn.title = `Switch to ${isLight ? 'dark' : 'light'} mode`;
  }
}

function toggleTheme() {
  const nextTheme = currentTheme === 'light' ? 'dark' : 'light';
  localStorage.setItem('novelverse-theme', nextTheme);
  applyTheme(nextTheme);
}

function initReaderFontSize() {
  const saved = Number(localStorage.getItem('novelverse-reader-font-size'));
  readerFontSize = Number.isFinite(saved) && saved >= 15 && saved <= 28 ? saved : 19;
  applyReaderFontSize();
}

function applyReaderFontSize() {
  document.documentElement.style.setProperty('--reader-font-size', `${readerFontSize}px`);
  const label = document.getElementById('readerFontSizeLabel');
  if (label) label.textContent = `${readerFontSize}px`;
}

function changeReaderFontSize(delta) {
  readerFontSize = Math.max(15, Math.min(28, readerFontSize + delta));
  localStorage.setItem('novelverse-reader-font-size', String(readerFontSize));
  applyReaderFontSize();
}

async function initSupabase() {
  try {
    const res = await fetch(`${API}/api/config/supabase`);
    const config = await res.json();
    if (!config.url || !config.publishableKey || !window.supabase) return;

    supabaseClient = window.supabase.createClient(config.url, config.publishableKey);
    window.supabaseClient = supabaseClient;
  } catch {}
}

// ── AUTH ──────────────────────────────────────────────────────────
async function checkAuth() {
  try {
    const res = await fetch(`${API}/api/me`, { credentials: 'include' });
    const data = await res.json();
    currentUser = data.user;
    updateAuthUI();
  } catch {}
}

function updateAuthUI() {
  const profileArea = document.getElementById('profileArea');
  const profileDropdownWrapper = document.getElementById('profileDropdownWrapper');

  if (currentUser) {
    profileArea.classList.add('hidden');
    profileDropdownWrapper.classList.remove('hidden');
    const init = currentUser.username[0].toUpperCase();
    document.getElementById('avatarCircle').textContent = init;
    document.getElementById('avatarLarge').textContent = init;
    document.getElementById('profileName').textContent = currentUser.username;
    document.getElementById('dropdownUsername').textContent = currentUser.username;
    document.getElementById('dropdownEmail').textContent = currentUser.email;
    document.getElementById('dropdownRole').textContent = currentUser.role === 'admin' ? '⚙ Administrator' : '✦ Member';

    // Show/hide admin links
    document.querySelectorAll('.admin-only').forEach(el => {
      if (currentUser.role === 'admin') el.classList.remove('hidden');
      else el.classList.add('hidden');
    });

    loadDropdownStats();
  } else {
    profileArea.classList.remove('hidden');
    profileDropdownWrapper.classList.add('hidden');
    document.querySelectorAll('.admin-only').forEach(el => el.classList.add('hidden'));
  }
}

async function loadDropdownStats() {
  try {
    const [favRes, libRes] = await Promise.all([
      fetch(`${API}/api/favorites`, { credentials: 'include' }),
      fetch(`${API}/api/library`, { credentials: 'include' })
    ]);
    const favs = await favRes.json();
    const lib = await libRes.json();
    document.getElementById('statFavs').textContent = Array.isArray(favs) ? favs.length : 0;
    document.getElementById('statLib').textContent = Array.isArray(lib) ? lib.length : 0;
  } catch {}
}

function toggleProfileDropdown() {
  const dd = document.getElementById('profileDropdown');
  dd.classList.toggle('hidden');
}

function closeDropdown() {
  document.getElementById('profileDropdown').classList.add('hidden');
}

document.addEventListener('click', (e) => {
  const wrapper = document.getElementById('profileDropdownWrapper');
  if (wrapper && !wrapper.contains(e.target)) closeDropdown();
});

async function handleLogin(e) {
  e.preventDefault();
  const email = document.getElementById('loginEmail').value;
  const password = document.getElementById('loginPassword').value;
  const errEl = document.getElementById('loginError');

  try {
    const res = await fetch(`${API}/api/login`, {
      method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) { showError(errEl, data.error); return; }
    currentUser = data.user;
    updateAuthUI();
    closeModal('loginModal');
    showToast(`Welcome back, ${data.user.username}! 👋`);
    document.getElementById('loginEmail').value = '';
    document.getElementById('loginPassword').value = '';
  } catch { showError(errEl, 'Connection error'); }
}

async function handleRegister(e) {
  e.preventDefault();
  const username = document.getElementById('regUsername').value;
  const email = document.getElementById('regEmail').value;
  const password = document.getElementById('regPassword').value;
  const errEl = document.getElementById('registerError');

  try {
    const res = await fetch(`${API}/api/register`, {
      method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password })
    });
    const data = await res.json();
    if (!res.ok) { showError(errEl, data.error); return; }
    currentUser = data.user;
    updateAuthUI();
    closeModal('registerModal');
    showToast(`Welcome to NovelVerse, ${data.user.username}! ✨`);
  } catch { showError(errEl, 'Connection error'); }
}

async function logout() {
  await fetch(`${API}/api/logout`, { method: 'POST', credentials: 'include' });
  currentUser = null;
  updateAuthUI();
  showPage('home');
  showToast('Signed out. See you again!');
  closeDropdown();
}

function requireLogin(page) {
  if (!currentUser) { openModal('loginModal'); return; }
  showPage(page);
}

// ── PAGES ─────────────────────────────────────────────────────────
function showPage(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(`page-${page}`).classList.add('active');
  document.querySelectorAll('.nav-link').forEach(l => {
    l.classList.toggle('active', l.dataset.page === page);
  });
  window.scrollTo(0, 0);

  if (page === 'library') loadLibrary();
  if (page === 'favorites') loadFavorites();
  if (page === 'admin') loadAdmin();
}

function showAdminIfAllowed() {
  if (!currentUser || currentUser.role !== 'admin') { showToast('Admin access only'); return; }
  showPage('admin');
}

// ── NOVELS ────────────────────────────────────────────────────────
async function loadNovels(search = '') {
  const grid = document.getElementById('novelsGrid');
  grid.innerHTML = '<div class="loading-placeholder">Loading stories…</div>';
  try {
    let url = `${API}/api/novels?genre=${currentGenre}&search=${encodeURIComponent(search)}`;
    const res = await fetch(url, { credentials: 'include' });
    const novels = await res.json();
    grid.innerHTML = '';
    if (!novels.length) {
      grid.innerHTML = '<div class="empty-state">No novels found</div>';
      return;
    }
    novels.forEach(n => grid.appendChild(createNovelCard(n)));
  } catch {
    grid.innerHTML = '<div class="empty-state">Failed to load novels</div>';
  }
}

function genreEmoji(genre) {
  const map = { fantasy:'🐉', 'sci-fi':'🚀', mystery:'🔍', romance:'🌹', thriller:'⚡', horror:'💀' };
  return map[genre] || '📖';
}

function coverImage(url, alt, className) {
  if (!url) return '';
  return `<img class="${className}" src="${esc(url)}" alt="${esc(alt)} cover" loading="lazy">`;
}

function createNovelCard(n) {
  const card = document.createElement('div');
  card.className = 'novel-card';
  card.onclick = () => openNovel(n.id);
  card.innerHTML = `
    <div class="card-cover cover-${n.genre || 'fantasy'}">
      ${coverImage(n.cover, n.title, 'cover-img')}
      <div class="card-cover-inner ${n.cover ? 'has-cover' : ''}">${genreEmoji(n.genre)}</div>
      <span class="card-genre-badge">${n.genre || 'fiction'}</span>
      <span class="card-status status-${n.status}">${n.status}</span>
    </div>
    <div class="card-body">
      <div class="card-title">${esc(n.title)}</div>
      <div class="card-author">by ${esc(n.author)}</div>
      <div class="card-desc">${esc(n.description || '')}</div>
    </div>
    <div class="card-footer">
      <span>📖 ${n.chapter_count || 0} chapters</span>
      <span>👁 ${n.views || 0} views</span>
    </div>`;
  return card;
}

async function openNovel(id) {
  currentNovelId = id;
  showPage('novel');
  const detail = document.getElementById('novelDetail');
  detail.innerHTML = '<div class="loading-placeholder">Loading novel…</div>';
  try {
    const res = await fetch(`${API}/api/novels/${id}`, { credentials: 'include' });
    const n = await res.json();
    renderNovelDetail(n);
  } catch { detail.innerHTML = '<div class="empty-state">Failed to load</div>'; }
}

function renderNovelDetail(n) {
  const detail = document.getElementById('novelDetail');
  const favBtn = currentUser ? `
    <button class="btn-sm ${n.is_favorited ? 'active' : ''}" id="favBtn" onclick="toggleFavorite(${n.id})">
      ${n.is_favorited ? '❤️ Favorited' : '♡ Favorite'}
    </button>
    <button class="btn-sm ${n.in_library ? 'active' : ''}" id="libBtn" onclick="toggleLibrary(${n.id})">
      ${n.in_library ? '📚 In Library' : '+ Add to Library'}
    </button>` : `
    <button class="btn-sm" onclick="openModal('loginModal')">♡ Favorite</button>
    <button class="btn-sm" onclick="openModal('loginModal')">+ Library</button>`;

  detail.innerHTML = `
    <div class="novel-detail-header">
      <div class="novel-cover-lg cover-${n.genre || 'fantasy'} ${n.cover ? 'has-cover-image' : ''}">
        ${coverImage(n.cover, n.title, 'cover-img')}
        <span class="${n.cover ? 'has-cover' : ''}">${genreEmoji(n.genre)}</span>
      </div>
      <div class="novel-meta">
        <h1>${esc(n.title)}</h1>
        <div class="author">${esc(n.author)}</div>
        <div class="novel-badges">
          <span class="card-genre-badge" style="position:static">${n.genre || 'fiction'}</span>
          <span class="card-status status-${n.status}" style="position:static">${n.status}</span>
        </div>
        <p class="novel-desc">${esc(n.description || '')}</p>
        <div class="novel-actions-row">
          ${n.chapters && n.chapters.length ? `<button class="btn-primary" onclick="openReader(${n.id}, 1)">▶ Start Reading</button>` : ''}
          ${favBtn}
        </div>
        <div style="margin-top:12px;font-size:13px;color:var(--text3);font-family:var(--ff-mono)">
          👁 ${n.views} views &nbsp;·&nbsp; ❤️ ${n.favorite_count} favorites &nbsp;·&nbsp; 📖 ${n.chapters ? n.chapters.length : 0} chapters
        </div>
      </div>
    </div>
    <div class="chapters-section">
      <h3>Chapters</h3>
      <div class="chapter-list">
        ${n.chapters && n.chapters.length ? n.chapters.map(c => `
          <div class="chapter-item" onclick="openReader(${n.id}, ${c.chapter_number})">
            <span class="ch-num">Ch. ${c.chapter_number}</span>
            <span class="ch-title">${esc(c.title)}</span>
            <span class="ch-date">${formatDate(c.created_at)}</span>
          </div>`).join('') : '<div style="color:var(--text3);padding:20px;text-align:center">No chapters yet</div>'}
      </div>
    </div>
    <div class="comments-section">
      <div class="comments-header">
        <h3>Comments</h3>
        <span id="commentCount">0</span>
      </div>
      ${currentUser ? `
        <form class="comment-form" onsubmit="handleCommentSubmit(event, ${n.id})">
          <textarea id="commentInput" rows="3" placeholder="Share your thoughts..." required></textarea>
          <button type="submit" class="btn-primary">Post Comment</button>
        </form>` : `
        <div class="comment-login">
          <button class="btn-sm" onclick="openModal('loginModal')">Sign in to comment</button>
        </div>`}
      <div class="comments-list" id="commentsList">
        <div class="loading-placeholder">Loading comments...</div>
      </div>
    </div>`;
  loadComments(n.id);
}

async function loadComments(novelId) {
  const list = document.getElementById('commentsList');
  const count = document.getElementById('commentCount');
  if (!list) return;
  try {
    const res = await fetch(`${API}/api/novels/${novelId}/comments`, { credentials: 'include' });
    const comments = await res.json();
    if (count) count.textContent = comments.length;
    if (!comments.length) {
      list.innerHTML = '<div class="empty-comments">No comments yet</div>';
      return;
    }
    list.innerHTML = comments.map(c => `
      <div class="comment-item">
        <div class="comment-meta">
          <strong>${esc(c.username)}</strong>
          <span>${formatDate(c.created_at)}</span>
        </div>
        <p>${esc(c.content)}</p>
      </div>
    `).join('');
  } catch {
    list.innerHTML = '<div class="empty-comments">Failed to load comments</div>';
  }
}

async function handleCommentSubmit(e, novelId) {
  e.preventDefault();
  const input = document.getElementById('commentInput');
  const content = input.value.trim();
  if (!content) return;
  const res = await fetch(`${API}/api/novels/${novelId}/comments`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content })
  });
  if (res.ok) {
    input.value = '';
    showToast('Comment added');
    loadComments(novelId);
  }
}

async function toggleFavorite(novelId) {
  if (!currentUser) { openModal('loginModal'); return; }
  const res = await fetch(`${API}/api/favorites/${novelId}`, { method: 'POST', credentials: 'include' });
  const data = await res.json();
  const btn = document.getElementById('favBtn');
  if (btn) {
    btn.className = `btn-sm ${data.favorited ? 'active' : ''}`;
    btn.textContent = data.favorited ? '❤️ Favorited' : '♡ Favorite';
  }
  showToast(data.favorited ? 'Added to favorites ❤️' : 'Removed from favorites');
  loadDropdownStats();
}

async function toggleLibrary(novelId) {
  if (!currentUser) { openModal('loginModal'); return; }
  const res = await fetch(`${API}/api/library/${novelId}`, { method: 'POST', credentials: 'include' });
  const data = await res.json();
  const btn = document.getElementById('libBtn');
  if (btn) {
    btn.className = `btn-sm ${data.in_library ? 'active' : ''}`;
    btn.textContent = data.in_library ? '📚 In Library' : '+ Add to Library';
  }
  showToast(data.in_library ? 'Added to library 📚' : 'Removed from library');
  loadDropdownStats();
}

// ── READER ────────────────────────────────────────────────────────
async function openReader(novelId, chapterNum) {
  currentNovelId = novelId;
  currentChapter = chapterNum;
  showPage('reader');
  loadChapter(novelId, chapterNum);
}

async function loadChapter(novelId, chapterNum) {
  const content = document.getElementById('readerContent');
  content.innerHTML = '<div class="loading-placeholder">Loading chapter…</div>';
  try {
    const res = await fetch(`${API}/api/novels/${novelId}/chapters/${chapterNum}`, { credentials: 'include' });
    const ch = await res.json();
    document.getElementById('readerChapterLabel').textContent =
      `${ch.novel_title} — Chapter ${ch.chapter_number}`;
    document.getElementById('prevChBtn').disabled = chapterNum <= 1;
    document.getElementById('nextChBtn').disabled = chapterNum >= ch.total_chapters;
    document.getElementById('readerBackBtn').onclick = () => openNovel(novelId);

    const paragraphs = ch.content.split('\n').filter(p => p.trim());
    content.innerHTML = `<h2>Chapter ${ch.chapter_number}: ${esc(ch.title)}</h2>` +
      paragraphs.map(p => `<p>${esc(p)}</p>`).join('');
    window.scrollTo(0, 0);
  } catch { content.innerHTML = '<div class="empty-state">Failed to load chapter</div>'; }
}

function navigateChapter(dir) {
  currentChapter += dir;
  loadChapter(currentNovelId, currentChapter);
}

function backFromReader() { openNovel(currentNovelId); }

// ── LIBRARY & FAVORITES ───────────────────────────────────────────
async function loadLibrary() {
  const grid = document.getElementById('libraryGrid');
  grid.innerHTML = '<div class="loading-placeholder">Loading…</div>';
  try {
    const res = await fetch(`${API}/api/library`, { credentials: 'include' });
    const items = await res.json();
    grid.innerHTML = '';
    if (!items.length) { grid.innerHTML = '<div class="empty-state">Your library is empty</div>'; return; }
    items.forEach(n => grid.appendChild(createNovelCard(n)));
  } catch {}
}

async function loadFavorites() {
  const grid = document.getElementById('favoritesGrid');
  grid.innerHTML = '<div class="loading-placeholder">Loading…</div>';
  try {
    const res = await fetch(`${API}/api/favorites`, { credentials: 'include' });
    const items = await res.json();
    grid.innerHTML = '';
    if (!items.length) { grid.innerHTML = '<div class="empty-state">No favorites yet</div>'; return; }
    items.forEach(n => grid.appendChild(createNovelCard(n)));
  } catch {}
}

// ── ADMIN ─────────────────────────────────────────────────────────
function adminTab(tab) {
  document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
  document.getElementById(`admin-${tab}`).classList.add('active');
  document.querySelectorAll('.admin-nav-item').forEach((l, i) => {
    l.classList.toggle('active', ['dashboard','novels','users'][i] === tab);
  });
  if (tab === 'novels') loadAdminNovels();
  if (tab === 'users') loadAdminUsers();
}

async function loadAdmin() {
  try {
    const res = await fetch(`${API}/api/admin/stats`, { credentials: 'include' });
    const stats = await res.json();
    document.getElementById('statsGrid').innerHTML = [
      ['📚', stats.total_novels, 'Novels'],
      ['📄', stats.total_chapters, 'Chapters'],
      ['👥', stats.total_users, 'Users'],
      ['👁', stats.total_views, 'Total Views'],
      ['❤️', stats.total_favorites, 'Favorites'],
    ].map(([icon, num, label]) => `
      <div class="stat-card">
        <div style="font-size:28px;margin-bottom:8px">${icon}</div>
        <div class="stat-num">${num}</div>
        <div class="stat-label">${label}</div>
      </div>`).join('');
  } catch {}
}

async function loadAdminNovels() {
  const wrap = document.getElementById('adminNovelsTable');
  try {
    const res = await fetch(`${API}/api/novels`, { credentials: 'include' });
    const novels = await res.json();
    wrap.innerHTML = `<table>
      <thead><tr><th>Title</th><th>Author</th><th>Genre</th><th>Status</th><th>Chapters</th><th>Views</th><th>Actions</th></tr></thead>
      <tbody>${novels.map(n => `
        <tr>
          <td><strong>${esc(n.title)}</strong></td>
          <td>${esc(n.author)}</td>
          <td><span class="card-genre-badge" style="position:static">${n.genre}</span></td>
          <td><span class="card-status status-${n.status}" style="position:static">${n.status}</span></td>
          <td>${n.chapter_count}</td>
          <td>${n.views}</td>
          <td>
            <div class="table-actions">
              <button class="btn-sm" onclick="openAddChapter(${n.id})">+ Chapter</button>
              <button class="btn-sm" onclick="openEditNovel(${n.id}, ${JSON.stringify(n).replace(/"/g,'&quot;')})">Edit</button>
              <button class="btn-sm btn-danger" onclick="adminDeleteNovel(${n.id})">Delete</button>
            </div>
          </td>
        </tr>`).join('')}
      </tbody>
    </table>`;
  } catch {}
}

async function loadAdminUsers() {
  const wrap = document.getElementById('adminUsersTable');
  try {
    const res = await fetch(`${API}/api/admin/users`, { credentials: 'include' });
    const users = await res.json();
    wrap.innerHTML = `<table>
      <thead><tr><th>Username</th><th>Email</th><th>Role</th><th>Joined</th><th>Actions</th></tr></thead>
      <tbody>${users.map(u => `
        <tr>
          <td><strong>${esc(u.username)}</strong></td>
          <td>${esc(u.email)}</td>
          <td><span style="color:${u.role==='admin'?'var(--gold)':'var(--text2)'}">${u.role}</span></td>
          <td style="font-family:var(--ff-mono);font-size:12px">${formatDate(u.created_at)}</td>
          <td>
            ${u.id !== currentUser?.id ? `<button class="btn-sm btn-danger" onclick="adminDeleteUser(${u.id})">Delete</button>` : '<span style="color:var(--text3);font-size:12px">You</span>'}
          </td>
        </tr>`).join('')}
      </tbody>
    </table>`;
  } catch {}
}

function openNovelForm() {
  document.getElementById('novelFormId').value = '';
  document.getElementById('novelFormTitle').textContent = 'Add Novel';
  document.getElementById('nfTitle').value = '';
  document.getElementById('nfAuthor').value = '';
  document.getElementById('nfDescription').value = '';
  document.getElementById('nfCover').value = '';
  document.getElementById('nfGenre').value = 'fantasy';
  document.getElementById('nfStatus').value = 'ongoing';
  openModal('novelFormModal');
}

function openEditNovel(id, novel) {
  document.getElementById('novelFormId').value = id;
  document.getElementById('novelFormTitle').textContent = 'Edit Novel';
  document.getElementById('nfTitle').value = novel.title;
  document.getElementById('nfAuthor').value = novel.author;
  document.getElementById('nfDescription').value = novel.description || '';
  document.getElementById('nfCover').value = novel.cover || '';
  document.getElementById('nfGenre').value = novel.genre || 'fantasy';
  document.getElementById('nfStatus').value = novel.status || 'ongoing';
  openModal('novelFormModal');
}

async function handleNovelForm(e) {
  e.preventDefault();
  const id = document.getElementById('novelFormId').value;
  const payload = {
    title: document.getElementById('nfTitle').value,
    author: document.getElementById('nfAuthor').value,
    description: document.getElementById('nfDescription').value,
    cover: document.getElementById('nfCover').value,
    genre: document.getElementById('nfGenre').value,
    status: document.getElementById('nfStatus').value,
  };
  const url = id ? `${API}/api/novels/${id}` : `${API}/api/novels`;
  const method = id ? 'PUT' : 'POST';
  try {
    const res = await fetch(url, {
      method, credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      closeModal('novelFormModal');
      showToast(id ? 'Novel updated ✓' : 'Novel created ✓');
      loadAdminNovels();
      loadNovels();
    }
  } catch {}
}

async function adminDeleteNovel(id) {
  openDeleteConfirm({
    title: 'Delete novel?',
    message: 'This will delete the novel, its chapters, comments, favorites, and library saves.',
    onConfirm: async () => {
      await fetch(`${API}/api/novels/${id}`, { method: 'DELETE', credentials: 'include' });
      showToast('Novel deleted');
      loadAdminNovels();
      loadNovels();
    }
  });
}

function openAddChapter(novelId) {
  document.getElementById('chFormNovelId').value = novelId;
  document.getElementById('chFormTitle').value = '';
  document.getElementById('chFormContent').value = '';
  openModal('chapterFormModal');
}

async function handleChapterForm(e) {
  e.preventDefault();
  const novelId = document.getElementById('chFormNovelId').value;
  const payload = {
    title: document.getElementById('chFormTitle').value,
    content: document.getElementById('chFormContent').value,
  };
  try {
    const res = await fetch(`${API}/api/novels/${novelId}/chapters`, {
      method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      closeModal('chapterFormModal');
      showToast('Chapter added ✓');
      loadAdminNovels();
    }
  } catch {}
}

async function adminDeleteUser(id) {
  openDeleteConfirm({
    title: 'Delete user?',
    message: 'This will delete the user and remove their comments, favorites, and library saves.',
    onConfirm: async () => {
      await fetch(`${API}/api/admin/users/${id}`, { method: 'DELETE', credentials: 'include' });
      showToast('User deleted');
      loadAdminUsers();
    }
  });
}

// ── FILTERS ───────────────────────────────────────────────────────
function filterGenre(genre) {
  currentGenre = genre;
  document.querySelectorAll('.genre-btn').forEach(b => {
    b.classList.toggle('active', b.textContent.toLowerCase() === (genre || 'all'));
  });
  loadNovels();
}

function debounceSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    loadNovels(document.getElementById('searchInput').value);
  }, 350);
}

// ── MODALS ────────────────────────────────────────────────────────
function openModal(id) {
  const el = document.getElementById(id);
  el.classList.remove('hidden');
  document.querySelectorAll('.form-error').forEach(e => e.classList.add('hidden'));
}

function closeModal(id) {
  document.getElementById(id).classList.add('hidden');
}

function closeModalOnOverlay(e, id) {
  if (e.target.classList.contains('modal-overlay')) closeModal(id);
}

function switchModal(from, to) {
  closeModal(from);
  openModal(to);
}

// ── UTILS ─────────────────────────────────────────────────────────
function openDeleteConfirm({ title, message, onConfirm }) {
  pendingDeleteAction = onConfirm;
  document.getElementById('deleteConfirmTitle').textContent = title;
  document.getElementById('deleteConfirmMessage').textContent = message;
  openModal('deleteConfirmModal');
}

async function confirmDeleteAction() {
  if (!pendingDeleteAction) return;
  const action = pendingDeleteAction;
  pendingDeleteAction = null;
  closeModal('deleteConfirmModal');
  await action();
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.remove('hidden');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.add('hidden'), 3000);
}

function showError(el, msg) {
  el.textContent = msg;
  el.classList.remove('hidden');
}

function esc(str) {
  return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function formatDate(str) {
  if (!str) return '';
  try { return new Date(str).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
  catch { return str; }
}
