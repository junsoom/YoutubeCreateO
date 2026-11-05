import re,html,sys
t=open(sys.argv[1],encoding='utf-8',errors='replace').read()
t=re.sub(r'(?s)<(script|style)[^>]*>.*?</\1>','',t)
t=re.sub(r'<br\s*/?>|</p>|</h\d>|</li>|</tr>','\n',t)
t=re.sub(r'<[^>]+>','',t);t=html.unescape(t);t=re.sub(r'[ \t]+',' ',t);t=re.sub(r'\n\s*\n+','\n',t)
print(t)
