import re

file_path = 'd:/AWS/anti aws text extractor/src/static/signup.html'
with open(file_path, 'r', encoding='utf-8') as f:
    html = f.read()

# Remove the SplashCursor canvas and script entirely
html = re.sub(r'<canvas id="fluid".*?</canvas>\s*<script>\s*\(function\(\) \{.*?\n\}\)\(\);\s*</script>\s*', '', html, flags=re.DOTALL)

# In case the SplashCursor script closing tag was formatted differently
html = re.sub(r'<canvas id="fluid".*?</canvas>\s*<script>.*?mainImage\(fc, gl_FragCoord\.xy\);\s*gl_FragColor = fc;\s*\}\s*</script>\s*', '', html, flags=re.DOTALL)

# Remove the DOMContentLoaded wrapper for LaserFlow just to ensure it runs immediately
laser_setup_start = "document.addEventListener('DOMContentLoaded', () => {"
laser_setup_replacement = """
(function initLaser() {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', runLaser);
  } else {
    runLaser();
  }

  function runLaser() {
"""

html = html.replace(laser_setup_start, laser_setup_replacement)
html = html.replace('  animate();\n});\n</script>', '  animate();\n  }\n})();\n</script>')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(html)
