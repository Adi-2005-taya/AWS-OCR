import re

with open('d:/AWS/anti aws text extractor/src/static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

lightbox_js = """
<script>
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
  setTimeout(() => { document.getElementById('lightbox-content').src = ''; }, 400);
}

document.addEventListener('keydown', (e) => {
  if(e.key === 'Escape') closeLightbox();
});
</script>
"""

if 'function openLightbox' not in html:
    html = html.replace('</body>', lightbox_js + '\n</body>')

old_str = "document.getElementById('drawer-doc-id').textContent=docId;"
new_str = "document.getElementById('drawer-doc-id').textContent=docId; currentDrawerDocId = docId; document.getElementById('btn-drawer-download').href = `/download/${docId}`;"

if 'currentDrawerDocId = docId' not in html:
    html = html.replace(old_str, new_str)

with open('d:/AWS/anti aws text extractor/src/static/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Patched JS logic.')
