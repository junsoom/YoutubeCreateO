import pypdf
r=pypdf.PdfReader('m1657.pdf')
with open('m1657.txt','w') as f:
    for i,p in enumerate(r.pages):
        f.write(f"\n\n#### PAGE {i+1}\n"+(p.extract_text() or ''))
