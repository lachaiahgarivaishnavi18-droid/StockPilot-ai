"""Configure cloud secrets in memory; stdout is consumed privately by the agent."""
import json
import secrets
from pathlib import Path
import httpx

root=Path(__file__).resolve().parent.parent
auth=json.loads((root/'.vercel-auth/auth.json').read_text())
project=json.loads((root/'.deployment/.vercel/project.json').read_text())
client=httpx.Client(base_url='https://api.vercel.com',headers={'Authorization':'Bearer '+auth['token']},params={'teamId':project['orgId']},timeout=30)
resource=client.get('/v1/storage/stores/store_V0VyT2KN0G5W2ZXM')
if resource.is_success:
    store=resource.json().get('store',resource.json())
    # Report only billing metadata, never connection strings.
    plan={k:store[k] for k in ('billingPlan','billingPlanId','plan') if k in store}
else: plan={'status':resource.status_code}
setup_token=secrets.token_urlsafe(40)
values={'APP_ENV':'production','JWT_SECRET':secrets.token_urlsafe(48),'BOOTSTRAP_TOKEN':setup_token}
for key,value in values.items():
    response=client.post(f"/v10/projects/{project['projectId']}/env",json={'key':key,'value':value,'type':'encrypted','target':['production','preview']})
    response.raise_for_status()
print(json.dumps({'configured':list(values),'setup_token':setup_token,'plan':plan}))
