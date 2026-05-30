import re

files = [
    'd:/AWS/anti aws text extractor/src/static/login.html',
    'd:/AWS/anti aws text extractor/src/static/signup.html'
]

for file_path in files:
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Replace the DOMContentLoaded wrapper in the module script with immediate execution
    old_init = """document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('hyperspeed-container');
    if (!container) return;
    const options = {
        ...DEFAULT_EFFECT_OPTIONS,
        distortion: distortions[DEFAULT_EFFECT_OPTIONS.distortion]
    };
    const myApp = new App(container, options);
    myApp.loadAssets().then(myApp.init);
});"""
    
    new_init = """const container = document.getElementById('hyperspeed-container');
if (container) {
    const options = {
        ...DEFAULT_EFFECT_OPTIONS,
        distortion: distortions[DEFAULT_EFFECT_OPTIONS.distortion]
    };
    const myApp = new App(container, options);
    myApp.loadAssets().then(myApp.init);
}"""

    # If it wasn't exact match due to formatting, use regex
    if old_init in html:
        html = html.replace(old_init, new_init)
    else:
        # Fallback regex
        html = re.sub(
            r"document\.addEventListener\('DOMContentLoaded',\s*\(\)\s*=>\s*\{(.*?)\}\);",
            r"\1",
            html,
            flags=re.DOTALL
        )
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html)
