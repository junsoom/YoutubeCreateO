from pypdf import PdfReader
r=PdfReader('/Users/junhyunglee/.hermes/cache/scratch/f19/hgram057.pdf')
t='\n'.join((p.extract_text() or '') for p in r.pages)
open('/Users/junhyunglee/.hermes/cache/scratch/f19/hgram057.txt','w').write(t)
i=t.find('Flight 19')
print(len(t))
