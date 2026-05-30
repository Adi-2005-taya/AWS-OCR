import re

files = [
    'd:/AWS/anti aws text extractor/src/static/login.html',
    'd:/AWS/anti aws text extractor/src/static/signup.html'
]

error_handler = """
<div id="debug-overlay" style="position: fixed; top: 0; left: 0; z-index: 9999; background: rgba(255,0,0,0.8); color: white; padding: 20px; width: 100vw; display: none; white-space: pre-wrap; font-family: monospace;"></div>
<script>
  window.addEventListener('error', function(event) {
    const dbg = document.getElementById('debug-overlay');
    if (dbg) {
      dbg.style.display = 'block';
      dbg.innerHTML += '<b>Error:</b> ' + event.message + '\\n' + '<b>File:</b> ' + event.filename + ':' + event.lineno + '\\n\\n';
    }
  });
  window.addEventListener('unhandledrejection', function(event) {
    const dbg = document.getElementById('debug-overlay');
    if (dbg) {
      dbg.style.display = 'block';
      dbg.innerHTML += '<b>Promise Rejection:</b> ' + (event.reason ? event.reason.toString() : 'Unknown error') + '\\n';
      if (event.reason && event.reason.stack) {
        dbg.innerHTML += '<b>Stack:</b> ' + event.reason.stack + '\\n\\n';
      }
    }
  });
</script>
"""

for file_path in files:
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # remove if already there
    html = re.sub(r'<div id="debug-overlay".*?</script>', '', html, flags=re.DOTALL)
    
    # insert right after <body>
    html = html.replace('<body>', '<body>\n' + error_handler)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html)
