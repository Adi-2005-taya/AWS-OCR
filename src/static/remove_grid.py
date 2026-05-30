import re

files = [
    'd:/AWS/anti aws text extractor/src/static/login.html',
    'd:/AWS/anti aws text extractor/src/static/signup.html'
]

for file_path in files:
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Remove the <div class="bg-grid"></div>
    html = re.sub(r'<div class="bg-grid"></div>\n?', '', html)
    
    # Also remove the debug overlay since the user didn't report an error, 
    # meaning the effect is now working.
    html = re.sub(r'<div id="debug-overlay".*?</script>\n?', '', html, flags=re.DOTALL)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html)
