"""Read-only recursive bounds audit of Wrath M2 animation descriptors."""
import json, struct, sys
from pathlib import Path

root = Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent/'candidate-v2'
results=[]
for path in sorted(root.rglob('*.m2')):
 b=path.read_bytes();issues=[];checks=[0]
 def u(p):return struct.unpack_from('<I',b,p)[0]
 def array(p,stride,label):
  n,o=struct.unpack_from('<II',b,p);checks[0]+=1
  if o>len(b) or o+n*stride>len(b):
   issues.append(dict(field=label,count=n,offset=o,stride=stride,size=len(b)))
   return 0,0
  return n,o
 seq,seqoff=array(28,64,'sequences')
 def track(p,stride,label,event=False):
  interp,loop=struct.unpack_from('<HH',b,p)
  descriptors=[(p+4,4,'times')]+([] if event else [(p+12,stride,'keys')])
  for desc,width,kind in descriptors:
   n,o=array(desc,8,label+'.'+kind)
   for i in range(n):
    if loop!=65535 or (i<seq and u(seqoff+i*64+12)&32):
     array(o+i*8,width,label+'.'+kind+'['+str(i)+']')
 def records(header,stride,fields,label):
  n,o=array(header,stride,label)
  for i in range(n):
   for offset,width in fields:track(o+i*stride+offset,width,f'{label}[{i}]+{offset}')
 records(44,88,[(16,12),(36,8),(56,12)],'bones')
 records(72,40,[(0,12),(20,2)],'colors')
 records(88,20,[(0,2)],'weights')
 records(96,60,[(0,12),(20,8),(40,12)],'transforms')
 records(240,40,[(20,1)],'attachments')
 records(264,156,[(16,12),(36,4),(56,12),(76,4),(96,4),(116,4),(136,1)],'lights')
 records(272,100,[(16,36),(48,36),(80,12)],'cameras')
 n,o=array(256,36,'events')
 for i in range(n):track(o+i*36+24,0,f'events[{i}]',True)
 results.append(dict(model=path.name,checks=checks[0],issues=issues))
print(json.dumps(results,indent=2))
sys.exit(any(x['issues'] for x in results))
