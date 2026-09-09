import datetime,hashlib,json,urllib.request,urllib.parse
from pathlib import Path
import argparse
parser=argparse.ArgumentParser(description='Explicit review-time fetch of five official metadata endpoints; never a build/runtime step')
parser.add_argument('--destination', type=Path, required=True)
out=parser.parse_args().destination
out.mkdir(parents=True, exist_ok=False)
base='https://firefox.settings.services.mozilla.com/v1'
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): raise RuntimeError('Unexpected redirect')
opener=urllib.request.build_opener(NoRedirect)
manifest=[]
for stem,url in [('capabilities',base+'/')]+[(f'{c}-{kind}',base+'/buckets/main/collections/'+c+suffix) for c in ['quicksuggest-amp','quicksuggest-other'] for kind,suffix in [('metadata',''),('records','/records')]]:
    page=0
    while url:
        assert urllib.parse.urlsplit(url).scheme=='https' and urllib.parse.urlsplit(url).netloc=='firefox.settings.services.mozilla.com'
        assert page<10
        with opener.open(urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'Redoubt-offline-Suggest-input-review/1'}),timeout=30) as response:
            data=response.read(8*1024*1024+1)
            assert len(data)<=8*1024*1024
            parsed=json.loads(data)
            path=f'{stem}{"-page"+str(page) if page else ""}.json'
            (out/path).write_bytes(data)
            manifest.append({'file':path,'url':url,'fetched_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':response.status,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'headers':dict(response.headers.items())})
            url=response.headers.get('Next-Page')
            page+=1
(out/'requests.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps([{k:v for k,v in m.items() if k not in ['headers']} for m in manifest],indent=2))
