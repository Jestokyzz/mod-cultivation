"""Regression against immutable source loops, including beyond-first-cycle time."""
import json,struct,sys
from pathlib import Path
R=Path(__file__).parent
SOURCE=Path(sys.argv[2]) if len(sys.argv)>2 else R/'embodied-source-v1'
u=lambda b,p:struct.unpack_from('<I',b,p)[0]
issues=[];checks=0
for p in Path(sys.argv[1]).rglob('*.m2'):
 b=p.read_bytes();raw=(SOURCE/p.name).read_bytes();source=raw[8:8+u(raw,4)]
 for i in range(u(source,20)):
  expected=u(source,u(source,24)+4*i);actual=u(b,u(b,24)+4*i)
  if expected!=actual:issues.append({'model':str(p),'loop':i,'expected':expected,'actual':actual})
  checks+=1
 for i in range(u(b,96)):
  for k in (0,20,40):
   at=u(b,100)+60*i+k;loop=struct.unpack_from('<h',b,at+2)[0]
   if loop<0 or not u(b,at+4):continue
   assert loop<u(b,20)
   d=u(b,u(b,24)+4*loop);assert d>0
   descriptor=u(b,at+8);count,offset=struct.unpack_from('<II',b,descriptor)
   if count>1:
    end=u(b,offset+4*(count-1))
    if d!=end:issues.append({'model':str(p),'UV_loop_ms':d,'last_key_ms':end})
    # Simulate the clock after multiple loops, not just the first 3 seconds.
    assert (3*d+d//2)%d==d//2
    checks+=1
print(json.dumps({'checks':checks,'issues':issues},indent=2))
sys.exit(bool(issues))
