import urllib.request
import re

req = urllib.request.Request("http://localhost:3000/integrations", headers={"User-Agent": "Mozilla/5.0"})
res = urllib.request.urlopen(req)
html = res.read().decode("utf-8")
print("HTML STATUS:", res.status)

css_files = re.findall(r'href="(/_next/static/css/[^"]+)"', html)
print("FOUND CSS FILES:", css_files)
for path in css_files:
    css_res = urllib.request.urlopen(f"http://localhost:3000{path}")
    content = css_res.read()
    print(f"  {path} -> HTTP {css_res.status}, Size: {len(content)} bytes")
