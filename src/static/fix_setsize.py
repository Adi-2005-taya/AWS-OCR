import re

files = [
    'd:/AWS/anti aws text extractor/src/static/login.html',
    'd:/AWS/anti aws text extractor/src/static/signup.html'
]

for file_path in files:
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # We need to add setSize method to App class. We'll add it right before onWindowResize()
    
    old_code = """  onWindowResize() {"""
    new_code = """  setSize(width, height, updateStyle) {
    this.renderer.setSize(width, height, updateStyle);
    this.composer.setSize(width, height);
  }
  onWindowResize() {"""
    
    html = html.replace(old_code, new_code)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html)
