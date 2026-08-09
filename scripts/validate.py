# -*- coding: utf-8 -*-
"""배포 전 정합성 검사. 실패 시 exit 1.

  py scripts/validate.py
"""
import re, sys, io, os, glob, json, urllib.parse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

files = [f.replace('\\', '/') for f in glob.glob('**/*.html', recursive=True) if '.git' not in f]
errors = []


def check(cond, msg):
    if not cond:
        errors.append(msg)


# 1) JSON-LD 파싱 — HTML 태그가 섞여 들어가는 사고를 잡는다
blocks = 0
for f in files:
    s = open(f, encoding='utf-8').read()
    for raw in re.findall(r'<script[^>]*ld\+json[^>]*>(.*?)</script>', s, re.S):
        blocks += 1
        try:
            json.loads(raw)
        except Exception as e:
            errors.append(f'JSON-LD 파싱 실패: {f} — {e}')
        if re.search(r'<a\s|</a>|<p>|<br', raw):
            errors.append(f'JSON-LD에 HTML 태그 혼입: {f}')

# 2) 필수 메타 — 페이지당 정확히 1개
for f in files:
    s = open(f, encoding='utf-8').read()
    for label, pat in [('title', r'<title>'), ('description', r'name="description"'),
                       ('canonical', r'rel="canonical"'), ('h1', r'<h1'),
                       ('og:image', r'property="og:image"')]:
        n = len(re.findall(pat, s))
        check(n == 1, f'{label} {n}개 (1개여야 함): {f}')

# 3) canonical 자기참조
for f in files:
    s = open(f, encoding='utf-8').read()
    m = re.search(r'href="([^"]+)"\s+rel="canonical"', s)
    want = 'https://tvbaro.kr/' + (f[:-len('index.html')] if f.endswith('index.html') else f)
    check(m and m.group(1) == want,
          f'canonical 불일치: {f} — {m.group(1) if m else "없음"} != {want}')

# 4) 사이트맵과 실제 파일 1:1
sm = open('sitemap.xml', encoding='utf-8').read()
locs = {urllib.parse.unquote(u).replace('https://tvbaro.kr', '') for u in re.findall(r'<loc>(.*?)</loc>', sm)}
paths = {'/' + (f[:-len('index.html')] if f.endswith('index.html') else f) for f in files}
for x in locs - paths:
    errors.append(f'사이트맵에만 존재(404 위험): {x}')
for x in paths - locs:
    errors.append(f'사이트맵 미등재: {x}')

# 5) 워드프레스 잔재 / 죽은 참조
for f in files:
    s = open(f, encoding='utf-8').read()
    for pat in ['/feed/', 'xmlrpc', 'wp-emoji', 'comments.min.css', 'comment-reply.min.js', '/author/']:
        check(pat not in s, f'죽은 참조 {pat}: {f}')

# 6) OG 이미지 파일 존재
for f in files:
    s = open(f, encoding='utf-8').read()
    for u in re.findall(r'property="og:image" content="https://tvbaro\.kr/([^"]+)"', s):
        check(os.path.exists(u), f'OG 이미지 없음: {u} ({f})')

# 7) 고아 페이지
inb = {('/' + (f[:-len('index.html')] if f.endswith('index.html') else f)): 0 for f in files}
for f in files:
    s = open(f, encoding='utf-8').read()
    src = '/' + (f[:-len('index.html')] if f.endswith('index.html') else f)
    for h in {urllib.parse.unquote(x).replace('https://tvbaro.kr', '')
              for x in re.findall(r'<a[^>]*href="([^"#]+)"', s)}:
        if h in inb and h != src:
            inb[h] += 1
for p, c in inb.items():
    check(c > 0, f'고아 페이지(유입 링크 0): {p}')

print(f'검사 대상: HTML {len(files)}개 / JSON-LD {blocks}블록')
if errors:
    print(f'\n실패 {len(errors)}건')
    for e in errors[:40]:
        print('  -', e)
    sys.exit(1)
print('통과: 모든 검사 정상')
