import re

with open("d:/AWS/anti aws text extractor/src/static/index.html", "r", encoding="utf-8") as f:
    html = f.read()

# 1. Add CSS
css_to_add = """
<style>
/* --- LIGHTBOX --- */
#lightbox-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.85); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  z-index: 100000; display: flex; align-items: center; justify-content: center;
  opacity: 0; pointer-events: none; transition: opacity 0.4s cubic-bezier(.34,1.56,.64,1);
}
#lightbox-overlay.open { opacity: 1; pointer-events: auto; }
#lightbox-content {
  max-width: 90vw; max-height: 90vh; border-radius: 12px; box-shadow: 0 20px 80px rgba(168,85,247,0.4);
  transform: scale(0.8) translateY(40px); transition: transform 0.4s cubic-bezier(.34,1.56,.64,1);
  object-fit: contain; border: 1px solid rgba(168,85,247,0.3);
}
#lightbox-overlay.open #lightbox-content { transform: scale(1) translateY(0); }
.lightbox-close {
  position: absolute; top: 2rem; right: 2rem; width: 44px; height: 44px; border-radius: 50%;
  background: rgba(168,85,247,0.15); color: #fff; border: 1px solid rgba(168,85,247,0.3);
  font-size: 1.5rem; display: flex; align-items: center; justify-content: center; cursor: pointer;
  transition: all 0.3s; z-index: 100001;
}
.lightbox-close:hover { background: rgba(168,85,247,0.4); transform: rotate(90deg); }

/* --- DOWNLOAD BUTTON --- */
.btn-download {
  display: flex; align-items: center; justify-content: center; gap: 0.5rem;
  width: 100%; padding: 0.8rem; margin-top: 1.5rem; border-radius: 10px;
  background: linear-gradient(135deg, rgba(168,85,247,0.1), rgba(124,58,237,0.1));
  border: 1px solid var(--p1); color: var(--p1); font-weight: 600; font-family: 'Space Grotesk', sans-serif;
  cursor: pointer; position: relative; overflow: hidden; transition: all 0.3s;
  box-shadow: 0 0 15px rgba(168,85,247,0.1); text-decoration: none;
}
.btn-download:hover {
  background: var(--p1); color: #fff; box-shadow: 0 0 30px rgba(168,85,247,0.4);
  transform: translateY(-2px);
}
.btn-download::before {
  content: ''; position: absolute; top: 0; left: -100%; width: 100%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
  transition: left 0.5s;
}
.btn-download:hover::before { left: 100%; }

/* --- VIEW ORIGINAL BUTTON --- */
.btn-view-original {
  display: flex; align-items: center; justify-content: center; gap: 0.5rem;
  width: 100%; padding: 0.8rem; margin-top: 0.5rem; border-radius: 10px;
  background: transparent;
  border: 1px solid rgba(168,85,247,0.3); color: var(--text); font-weight: 600; font-family: 'Space Grotesk', sans-serif;
  cursor: pointer; transition: all 0.3s;
}
.btn-view-original:hover {
  border-color: var(--p1); background: rgba(168,85,247,0.1);
}

/* --- DRAG DROP ENHANCEMENTS --- */
.drop-zone.drag-over {
  border: 2px solid var(--p1); background: rgba(168,85,247,0.15);
  box-shadow: 0 0 40px rgba(168,85,247,0.3), inset 0 0 40px rgba(168,85,247,0.1);
}
.drop-zone.drag-over .dz-icon {
  animation: dropIconDown 0.4s forwards;
}
@keyframes dropIconDown {
  to { transform: translateY(15px) scale(1.2); color: var(--p1); text-shadow: 0 0 15px var(--p1); }
}

/* --- SKELETON LOADERS --- */
.skeleton-card {
  display: flex; align-items: center; gap: 1rem;
  background: rgba(168,85,247,0.02); border: 1px solid rgba(168,85,247,0.1);
  border-radius: 14px; padding: 0.85rem 1rem; margin-bottom: 0.6rem;
  position: relative; overflow: hidden;
}
.skeleton-card::before {
  content: ''; position: absolute; inset: 0;
  background: linear-gradient(90deg, transparent, rgba(168,85,247,0.08), transparent);
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }
.skel-icon { width: 34px; height: 34px; border-radius: 8px; background: rgba(168,85,247,0.1); }
.skel-lines { flex: 1; display: flex; flex-direction: column; gap: 6px; }
.skel-line { height: 12px; border-radius: 6px; background: rgba(168,85,247,0.1); }
.skel-line.w-40 { width: 40%; }
.skel-line.w-80 { width: 80%; }
.skel-line.w-20 { width: 20%; }

/* --- EMPTY STATE ANIMATION --- */
.empty-state-wrap {
  text-align: center; padding: 3rem 1rem;
  animation: fadeUp 0.5s ease both;
}
.es-svg {
  width: 80px; height: 80px; margin: 0 auto 1rem;
  filter: drop-shadow(0 10px 20px rgba(168,85,247,0.3));
  animation: floatFolder 4s ease-in-out infinite;
}
.es-svg path { fill: url(#esGrad); }
@keyframes floatFolder { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-15px); } }
.es-title { font-family: 'Space Grotesk', sans-serif; font-size: 1.1rem; color: var(--text); font-weight: 700; margin-bottom: 0.4rem; }
.es-sub { font-size: 0.82rem; color: var(--muted); }

/* --- TOAST PROGRESS --- */
.toast-progress-wrap {
  position: absolute; bottom: 0; left: 0; right: 0; height: 3px;
  background: rgba(168,85,247,0.1); border-radius: 0 0 14px 14px; overflow: hidden;
}
.toast-progress-bar {
  height: 100%; background: linear-gradient(90deg, #a855f7, #e879f9); width: 100%;
}
.toast-progress-bar.animate {
  animation: drainToast var(--toast-dur, 3s) linear forwards;
}
@keyframes drainToast { from { width: 100%; } to { width: 0%; } }
#toast { padding-bottom: 1.2rem; } /* Make room for the bar */

</style>
"""

# Inject CSS before </head>
html = html.replace('</head>', css_to_add + '\n</head>')

# 2. Add Lightbox HTML before </body>
lightbox_html = """
<div id="lightbox-overlay" onclick="closeLightbox()">
  <button class="lightbox-close" onclick="closeLightbox(event)">&#10005;</button>
  <img id="lightbox-content" src="" alt="Document Preview" onclick="event.stopPropagation()">
</div>

<svg width="0" height="0" style="position:absolute">
  <defs>
    <linearGradient id="esGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#a855f7" />
      <stop offset="100%" stop-color="#e879f9" />
    </linearGradient>
  </defs>
</svg>
"""
html = html.replace('</body>', lightbox_html + '\n</body>')

# 3. Add Buttons inside Drawer HTML
# Find <div id="drawer-page-nav" ...></div>
drawer_buttons = """
<div id="drawer-page-nav" style="display:flex;flex-wrap:wrap;gap:.4rem;margin-bottom:1.25rem"></div>
      <a href="#" id="btn-drawer-download" class="btn-download" download>
        <span style="font-size:1.2rem;">&#10515;</span> Download Original
      </a>
      <button id="btn-drawer-preview" class="btn-view-original" onclick="openLightbox()">
        <span style="font-size:1.1rem;">&#128065;</span> View Fullscreen
      </button>
"""
html = html.replace('<div id="drawer-page-nav" style="display:flex;flex-wrap:wrap;gap:.4rem;margin-bottom:1.25rem"></div>', drawer_buttons)


# 4. Inject JS logic
# Replace the toast HTML structure
old_toast = '<div id="toast"><span id="toast-icon"></span><span id="toast-msg"></span></div>'
new_toast = """<div id="toast">
  <span id="toast-icon"></span><span id="toast-msg"></span>
  <div class="toast-progress-wrap"><div id="toast-progress-bar" class="toast-progress-bar"></div></div>
</div>"""
html = html.replace(old_toast, new_toast)

# Replace showToast JS
old_showToast = """function showToast(msg, isError=false){
  const t=document.getElementById('toast');
  document.getElementById('toast-msg').textContent=msg;
  document.getElementById('toast-icon').textContent=isError?'dY"':'dY"';
  t.className=`show ${isError?'err':'ok'}`;
  setTimeout(()=>t.className='', 3000);
}"""

new_showToast = """function showToast(msg, isError=false){
  const t=document.getElementById('toast');
  document.getElementById('toast-msg').textContent=msg;
  document.getElementById('toast-icon').textContent=isError?'dY"':'dY"';
  t.className=`show ${isError?'err':'ok'}`;
  
  const pBar = document.getElementById('toast-progress-bar');
  pBar.classList.remove('animate');
  void pBar.offsetWidth; // trigger reflow
  pBar.classList.add('animate');
  
  setTimeout(()=>t.className='', 3000);
}"""
html = html.replace(old_showToast, new_showToast)

# Inject empty state and skeletons in renderDocuments
old_renderDocs = """function renderDocuments(){
  const list=document.getElementById('doc-list');
  if(!docsCache.length){
    list.innerHTML='<div style="text-align:center;padding:2rem;color:var(--muted);font-size:.85rem">No documents found.</div>';
    return;
  }
  list.innerHTML='';"""

new_renderDocs = """function renderDocuments(){
  const list=document.getElementById('doc-list');
  if(!docsCache.length){
    list.innerHTML=`
      <div class="empty-state-wrap">
        <svg class="es-svg" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M22 19C22 20.1046 21.1046 21 20 21H4C2.89543 21 2 20.1046 2 19V6C2 4.89543 2.89543 4 4 4H9.17157C9.70201 4 10.2107 4.21071 10.5858 4.58579L12.4142 6.41421C12.7893 6.78929 13.298 7 13.8284 7H20C21.1046 7 22 7.89543 22 9V19Z" fill="#a855f7"/>
        </svg>
        <h3 class="es-title">No documents yet</h3>
        <p class="es-sub">Drag and drop a file above to get started.</p>
      </div>
    `;
    return;
  }
  list.innerHTML='';"""
html = html.replace(old_renderDocs, new_renderDocs)

# Add Lightbox JS
lightbox_js = """
// --- LIGHTBOX LOGIC ---
let currentDrawerDocId = null;

function openLightbox() {
  if(!currentDrawerDocId) return;
  const overlay = document.getElementById('lightbox-overlay');
  const img = document.getElementById('lightbox-content');
  img.src = `/download/${currentDrawerDocId}`;
  overlay.classList.add('open');
}

function closeLightbox(e) {
  if(e) e.stopPropagation();
  const overlay = document.getElementById('lightbox-overlay');
  overlay.classList.remove('open');
  // clear src to stop loading if needed
  setTimeout(() => { document.getElementById('lightbox-content').src = ''; }, 400);
}

document.addEventListener('keydown', (e) => {
  if(e.key === 'Escape') closeLightbox();
});
"""

html = html.replace('// Initialize', lightbox_js + '\n// Initialize')

# Make sure we set currentDrawerDocId in openDocDrawer and update the download button
old_openDocDrawer = """document.getElementById('drawer-doc-id').textContent=docId;"""
new_openDocDrawer = """document.getElementById('drawer-doc-id').textContent=docId;
  currentDrawerDocId = docId;
  document.getElementById('btn-drawer-download').href = `/download/${docId}`;"""
html = html.replace(old_openDocDrawer, new_openDocDrawer)

# Add skeleton loader injection before fetching documents
fetch_docs_logic_old = """async function fetchDocuments(){
  try{
    const res=await fetch('/documents');"""

fetch_docs_logic_new = """async function fetchDocuments(){
  const list=document.getElementById('doc-list');
  list.innerHTML = Array(3).fill(`
    <div class="skeleton-card">
      <div class="skel-icon"></div>
      <div class="skel-lines">
        <div class="skel-line w-40"></div>
        <div class="skel-line w-80"></div>
        <div class="skel-line w-20"></div>
      </div>
    </div>
  `).join('');
  
  try{
    const res=await fetch('/documents');"""
html = html.replace(fetch_docs_logic_old, fetch_docs_logic_new)

fetch_search_old = """async function runSearch(query){
  if(!query) return fetchDocuments();
  try{
    const res=await fetch(`/search?query=${encodeURIComponent(query)}`);"""

fetch_search_new = """async function runSearch(query){
  if(!query) return fetchDocuments();
  const list=document.getElementById('doc-list');
  list.innerHTML = Array(2).fill(`
    <div class="skeleton-card">
      <div class="skel-icon"></div>
      <div class="skel-lines">
        <div class="skel-line w-40"></div>
        <div class="skel-line w-80"></div>
      </div>
    </div>
  `).join('');
  
  try{
    const res=await fetch(`/search?query=${encodeURIComponent(query)}`);"""
html = html.replace(fetch_search_old, fetch_search_new)

with open("d:/AWS/anti aws text extractor/src/static/index.html", "w", encoding="utf-8") as f:
    f.write(html)
print("Injected UI components successfully.")
