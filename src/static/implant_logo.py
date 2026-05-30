import os
import glob

static_dir = r"d:\AWS\anti aws text extractor\src\static"
html_files = glob.glob(os.path.join(static_dir, "*.html"))

for fpath in html_files:
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    if '<link rel="icon"' not in content:
        content = content.replace("<head>", "<head>\n<link rel=\"icon\" href=\"/static/docusense-logo.jpg\" type=\"image/jpeg\">\n<meta property=\"og:image\" content=\"/static/docusense-logo.jpg\">")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated {os.path.basename(fpath)}")
