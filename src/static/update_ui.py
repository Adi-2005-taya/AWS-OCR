import re
import os

new_css = '''
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet"/>
<style>
  :root {
    --bg: #030014;
    --surface: rgba(24, 24, 27, 0.4);
    --border: rgba(255, 255, 255, 0.08);
    --border-focus: rgba(168, 85, 247, 0.5);
    --text: #f8fafc;
    --text-muted: #94a3b8;
    --accent: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
    --accent-text: #ffffff;
    --danger: #ef4444;
  }

  :root[data-theme="light"] {
    --bg: #f8fafc;
    --surface: rgba(255, 255, 255, 0.7);
    --border: rgba(0, 0, 0, 0.08);
    --border-focus: rgba(168, 85, 247, 0.5);
    --text: #0f172a;
    --text-muted: #64748b;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Inter', sans-serif;
    background-color: var(--bg);
    color: var(--text);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    overflow-x: hidden;
    position: relative;
    padding: 2rem 1.5rem;
  }

  /* Aurora Background */
  .aurora-bg {
    position: fixed;
    top: 0; left: 0; width: 100vw; height: 100vh;
    z-index: -2;
    overflow: hidden;
    background: var(--bg);
  }
  .aurora-blob {
    position: absolute;
    filter: blur(100px);
    opacity: 0.5;
    animation: float 20s infinite ease-in-out alternate;
    border-radius: 50%;
  }
  .aurora-blob:nth-child(1) {
    top: -10%; left: -10%; width: 50vw; height: 50vw;
    background: #6366f1;
    animation-delay: 0s;
  }
  .aurora-blob:nth-child(2) {
    bottom: -20%; right: -10%; width: 60vw; height: 60vw;
    background: #a855f7;
    animation-delay: -5s;
  }
  .aurora-blob:nth-child(3) {
    top: 40%; left: 50%; width: 40vw; height: 40vw;
    background: #ec4899;
    animation-delay: -10s;
  }

  @keyframes float {
    0% { transform: translate(0, 0) scale(1); }
    33% { transform: translate(30px, -50px) scale(1.1); }
    66% { transform: translate(-20px, 20px) scale(0.9); }
    100% { transform: translate(0, 0) scale(1); }
  }

  /* Grid overlay */
  .bg-grid {
    position: fixed; inset: 0; z-index: -1;
    background-image: 
      linear-gradient(to right, var(--border) 1px, transparent 1px),
      linear-gradient(to bottom, var(--border) 1px, transparent 1px);
    background-size: 40px 40px;
    mask-image: radial-gradient(circle at center, black 40%, transparent 100%);
    -webkit-mask-image: radial-gradient(circle at center, black 40%, transparent 100%);
  }

  .brand {
    display: flex; flex-direction: column; align-items: center;
    gap: 0.75rem; margin-bottom: 2rem;
    animation: fadeDown 0.8s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .brand-icon {
    width: 52px; height: 52px; border-radius: 16px;
    background: var(--accent);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.5rem;
    box-shadow: 0 10px 30px -5px rgba(168,85,247,0.6);
    border: 1px solid rgba(255,255,255,0.2);
  }

  .brand-name {
    font-family: 'Outfit', sans-serif;
    font-size: 1.8rem; font-weight: 700; letter-spacing: -0.04em;
    background: var(--accent); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }

  @keyframes fadeDown {
    from { opacity: 0; transform: translateY(-20px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .auth-card {
    background: var(--surface);
    backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
    border: 1px solid var(--border);
    border-radius: 24px;
    padding: 2.5rem; width: 100%; max-width: 420px;
    box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);
    animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1);
    position: relative;
  }
  
  .auth-card::before {
    content: ''; position: absolute; inset: 0; border-radius: 24px; padding: 1px;
    background: linear-gradient(135deg, rgba(255,255,255,0.15), rgba(255,255,255,0));
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor; mask-composite: exclude; pointer-events: none;
  }

  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .auth-header { text-align: center; margin-bottom: 2rem; }
  .auth-title {
    font-family: 'Outfit', sans-serif;
    font-size: 1.6rem; font-weight: 600; margin-bottom: 0.5rem;
    color: var(--text);
  }
  .auth-sub { color: var(--text-muted); font-size: 0.95rem; }

  .field { margin-bottom: 1.25rem; }
  .field label {
    display: block; font-size: 0.75rem; font-weight: 600;
    color: var(--text-muted); margin-bottom: 0.5rem;
    text-transform: uppercase; letter-spacing: 0.05em;
  }
  
  .input-wrapper { position: relative; }
  
  .field input {
    width: 100%; padding: 0.875rem 1rem 0.875rem 2.75rem;
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid var(--border); border-radius: 12px;
    color: var(--text); font-size: 0.95rem; font-family: inherit;
    transition: all 0.3s ease;
  }
  
  :root[data-theme="light"] .field input { background: rgba(255,255,255,0.5); }

  .field input:focus {
    outline: none; border-color: var(--border-focus); background: rgba(0, 0, 0, 0.4);
    box-shadow: 0 0 0 4px rgba(168, 85, 247, 0.15);
  }

  .field-icon {
    position: absolute; left: 1rem; top: 50%; transform: translateY(-50%);
    color: var(--text-muted); transition: color 0.3s;
  }
  .field:focus-within .field-icon { color: #a855f7; }

  .btn-submit {
    width: 100%; padding: 0.875rem; border: none; border-radius: 12px;
    font-size: 0.95rem; font-weight: 600; background: var(--accent); color: var(--accent-text);
    cursor: pointer; transition: all 0.3s ease;
    display: flex; justify-content: center; align-items: center; gap: 0.5rem;
    position: relative; overflow: hidden; margin-top: 0.5rem;
  }
  
  .btn-submit::before {
    content: ''; position: absolute; top: 0; left: -100%; width: 100%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
    transition: 0.5s;
  }
  .btn-submit:hover::before { left: 100%; }
  
  .btn-submit:hover { transform: translateY(-2px); box-shadow: 0 10px 20px -10px rgba(168,85,247,0.8); }
  .btn-submit:active { transform: translateY(0); }
  .btn-submit:disabled { opacity: 0.6; cursor: not-allowed; transform: none; box-shadow: none; filter: saturate(0.5); }

  .btn-google {
    width: 100%; padding: 0.875rem; border: 1px solid var(--border); border-radius: 12px;
    background: rgba(255,255,255,0.02); color: var(--text);
    font-size: 0.95rem; font-weight: 500; font-family: inherit;
    display: flex; align-items: center; justify-content: center; gap: 0.75rem;
    cursor: pointer; transition: all 0.3s ease; margin-bottom: 1rem;
  }
  .btn-google:hover { background: rgba(255,255,255,0.06); border-color: rgba(255,255,255,0.2); transform: translateY(-1px); }

  .divider {
    display: flex; align-items: center; gap: 1rem; margin: 1.5rem 0;
    color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;
  }
  .divider::before, .divider::after { content: ''; flex: 1; height: 1px; background: var(--border); }

  .forgot-link {
    display: block; text-align: right; font-size: 0.8rem; color: var(--text-muted);
    text-decoration: none; margin-top: -0.5rem; margin-bottom: 1.5rem; transition: color 0.2s;
  }
  .forgot-link:hover { color: #a855f7; }

  .auth-footer { text-align: center; margin-top: 1.5rem; font-size: 0.875rem; color: var(--text-muted); }
  .auth-footer a { color: #a855f7; text-decoration: none; font-weight: 500; transition: color 0.2s; }
  .auth-footer a:hover { color: #c084fc; text-decoration: underline; }

  .theme-pill {
    position: fixed; top: 1.5rem; right: 1.5rem; padding: 0.5rem 1rem; border-radius: 20px;
    background: var(--surface); border: 1px solid var(--border);
    color: var(--text); font-size: 0.8rem; font-weight: 500; cursor: pointer;
    backdrop-filter: blur(12px); transition: all 0.2s; z-index: 50;
  }
  .theme-pill:hover { border-color: var(--border-focus); transform: scale(1.05); }

  .error-box {
    background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: 12px; padding: 0.875rem; font-size: 0.85rem; color: var(--danger);
    margin-bottom: 1rem; display: none; animation: fadeUp 0.3s ease; text-align: center;
  }
  
  .spin { width: 16px; height: 16px; border-radius: 50%; border: 2px solid rgba(255, 255, 255, 0.2); border-top-color: currentColor; animation: spin 0.6s linear infinite; display: none; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Signup specific */
  .pw-strength { margin-top: 0.5rem; height: 4px; border-radius: 4px; background: rgba(255,255,255,0.1); overflow: hidden; }
  .pw-strength-fill { height: 100%; border-radius: 4px; transition: width 0.4s ease, background 0.4s ease; width: 0%; }
  .pw-hint { font-size: 0.75rem; font-weight: 500; color: var(--text-muted); margin-top: 0.4rem; display: flex; align-items: center; gap: 0.25rem; }
  
  .terms-agreement { margin: 1.25rem 0; display: flex; align-items: center; }
  .custom-checkbox { display: flex; align-items: center; position: relative; padding-left: 28px; cursor: pointer; font-size: 0.8rem; color: var(--text-muted); user-select: none; }
  .custom-checkbox input { position: absolute; opacity: 0; cursor: pointer; height: 0; width: 0; }
  .checkmark { position: absolute; top: 50%; left: 0; transform: translateY(-50%); height: 18px; width: 18px; background-color: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: 6px; transition: all 0.2s; }
  .custom-checkbox:hover input ~ .checkmark { border-color: var(--border-focus); }
  .custom-checkbox input:checked ~ .checkmark { background: #a855f7; border-color: transparent; box-shadow: 0 0 10px rgba(168,85,247,0.4); }
  .checkmark:after { content: ""; position: absolute; display: none; left: 6px; top: 2.5px; width: 4px; height: 8px; border: solid white; border-width: 0 2px 2px 0; transform: rotate(45deg); }
  .custom-checkbox input:checked ~ .checkmark:after { display: block; }
  .custom-checkbox a { color: var(--text); text-decoration: underline; font-weight: 500; transition: color 0.2s; }
  .custom-checkbox a:hover { color: #a855f7; }
</style>
'''

bg_html = '''
<div class="aurora-bg">
  <div class="aurora-blob"></div>
  <div class="aurora-blob"></div>
  <div class="aurora-blob"></div>
</div>
<div class="bg-grid"></div>
'''

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    # Replace fonts and styles
    html = re.sub(r'<link href="https://fonts.googleapis.com/css2[^>]*>', '', html)
    html = re.sub(r'<style>.*?</style>', new_css, html, flags=re.DOTALL)

    # Replace canvas
    html = re.sub(r'<canvas id="bg-canvas"></canvas>', bg_html, html)

    # Remove WebGL script
    html = re.sub(r'// ── WebGL Fluid Simulation Background Engine ──────────────────.*?initWebGL\(\);', '', html, flags=re.DOTALL)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

process_file('d:/AWS/anti aws text extractor/src/static/login.html')
process_file('d:/AWS/anti aws text extractor/src/static/signup.html')
print('Done processing files!')
