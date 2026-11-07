"""Read-only smoke checks for the public production deployment."""
from html.parser import HTMLParser
import httpx

class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts=[]
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag=='script' and 'src' in values:
            self.scripts.append(values['src'])

base='https://stockpilot-ai-black.vercel.app'
with httpx.Client(base_url=base,timeout=60) as client:
    response=client.get('/',headers={'Accept':'text/html'})
    response.raise_for_status()
    parser=Assets();parser.feed(response.text)
    assets=[client.get(path) for path in parser.scripts]
    assert assets and all(r.status_code==200 for r in assets)
    assert any('CLOUD WORKSPACE' in r.text for r in assets)
    assert client.get('/api/health').json()['status']=='ok'
    assert client.get('/demand-forecasting',headers={'Accept':'text/html'}).status_code==200
    assert client.get('/api/inventory').status_code==401
print('Production smoke checks passed: homepage, JavaScript assets, cloud labels, API health, SPA deep link, authentication.')
