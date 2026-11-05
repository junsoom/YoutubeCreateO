import sys, os, urllib.request, time
from PIL import Image
D = '/Users/junhyunglee/.hermes/cache/scratch/f19/img/'
def get(n):
    fn = D + f'p{n:03d}.jpg'
    if not os.path.exists(fn):
        req = urllib.request.Request(f'https://catalog.archives.gov/medialz/fort-worth/rg-181/M1657-001/M1657-001-{n:03d}.jpg', headers={'User-Agent': 'Mozilla/5.0'})
        open(fn, 'wb').write(urllib.request.urlopen(req, timeout=60).read())
    return fn
a, b = int(sys.argv[1]), int(sys.argv[2])
ims = []
for n in range(a, b + 1):
    try:
        ims.append((n, Image.open(get(n)).convert('L')))
    except Exception as e:
        print('fail', n, e)
cols = 4
w = 480
rows = (len(ims) + cols - 1) // cols
h = int(w * 4072 / 3112)
sheet = Image.new('L', (cols * w, rows * (h + 20)), 255)
from PIL import ImageDraw
dr = ImageDraw.Draw(sheet)
for i, (n, im) in enumerate(ims):
    t = im.resize((w, h))
    x, y = (i % cols) * w, (i // cols) * (h + 20)
    sheet.paste(t, (x, y + 20))
    dr.text((x + 5, y + 3), str(n), fill=0)
out = D + f'sheet_{a}_{b}.jpg'
sheet.save(out, quality=80)
print(out, sheet.size)
