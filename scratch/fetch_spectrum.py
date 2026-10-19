import requests
import re
import os

url = 'https://spectrummap.kr/cop/bbs/selectBoardArticle.do?menuNo=300588&bbsId=BBSMSTR_000000000172&nttId=14341&menuNo=300510&gubun=1'
res = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
print('Status:', res.status_code, 'Length:', len(res.text))

os.makedirs('temp', exist_ok=True)
with open('temp/spectrum_raw.html', 'w', encoding='utf-8') as f:
    f.write(res.text)

# Search for api url or parameters in the html
matches = re.findall(r'https?://[^\s"\'<>]+', res.text)
for m in set(matches):
    if any(k in m for k in ['api', 'openapi', 'data.go.kr', 'service']):
        print('URL match:', m)

# Search text inside body
clean_text = re.sub(r'<script.*?</script>', '', res.text, flags=re.DOTALL | re.IGNORECASE)
clean_text = re.sub(r'<style.*?</style>', '', clean_text, flags=re.DOTALL | re.IGNORECASE)
clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
lines = [line.strip() for line in clean_text.splitlines() if line.strip()]

with open('temp/spectrum_text.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print('Saved spectrum_text.txt with', len(lines), 'lines')
