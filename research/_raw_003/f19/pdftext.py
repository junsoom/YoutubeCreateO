from pypdf import PdfReader
r = PdfReader('/Users/junhyunglee/.hermes/cache/scratch/f19/m1657.pdf')
print('pages', len(r.pages))
out = open('/Users/junhyunglee/.hermes/cache/scratch/f19/m1657.txt', 'w')
tot = 0
for i, p in enumerate(r.pages):
    try:
        t = p.extract_text() or ''
    except Exception as e:
        t = f'ERR {e}'
    tot += len(t)
    out.write(f'\n\n===== PAGE {i+1} =====\n{t}')
out.close()
print('chars', tot)
