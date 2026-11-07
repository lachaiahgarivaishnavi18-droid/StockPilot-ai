import {test,expect,type Page} from '@playwright/test';

async function mockWorkspace(page:Page,role='admin',initialLoaded=false){
 let loaded=initialLoaded;
 let historyReads=0;
 const user={id:1,name:'Test operator',role,email:'test@example.invalid'};
 await page.route('**/api/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  let response:any={};
  if(path==='/api/auth/login')response={access_token:'isolated-ui-test-token',user};
  else if(path==='/api/auth/me')response=user;
  else if(path==='/api/products')response={items:loaded?[{id:1,sku:'TEST-1',name:'Test product'}]:[],total:loaded?1:0};
  else if(path==='/api/reports')response={inventory:[],alerts:[],summary:{}};
  else if(path==='/api/analytics/summary')response={forecasted_demand:0,replenishment_recommendations:0};
  else if(path==='/api/agents/executions')response=[];
  else if(path==='/api/agents/run')response={id:1,status:'awaiting_approval',data:{outputs:{purchase_order:{id:123,quantity:100}}}};
  else if(path==='/api/demo/load'){loaded=true;response={loaded:true,products:1,daily_sales:60}}
  else if(path==='/api/sales/history/1'){
   historyReads++;
   response=loaded?Array.from({length:60},(_,i)=>({date:new Date(Date.UTC(2026,0,i+1)).toISOString().slice(0,10),quantity:10})):[];
  }
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(response)});
 });
 await page.goto('/demand-forecasting');
 await page.getByLabel('Email address').fill(user.email);
 await page.getByLabel('Password',{exact:true}).fill('Isolated-ui-test-password');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Demand Forecasting',exact:true})).toBeVisible();
 return ()=>historyReads;
}

test('sample load refreshes history for an unchanged selected product and enables forecasting',async({page})=>{
 const reads=await mockWorkspace(page);
 const generate=page.getByRole('button',{name:'Generate & evaluate',exact:true});
 await expect(generate).toBeDisabled();
 await expect.poll(reads).toBeGreaterThan(0);
 const before=reads();
 await page.getByRole('button',{name:'Load sample data',exact:true}).click();
 await expect(page.getByLabel('Selected product')).toHaveValue('1');
 await expect(generate).toBeEnabled();
 await expect.poll(reads).toBeGreaterThan(before);
 await expect(page.getByText(/No products loaded/)).toHaveCount(0);
});

test('an analyst is told why sample loading is unavailable',async({page})=>{
 await mockWorkspace(page,'analyst');
 const loader=page.getByRole('button',{name:'Load sample data',exact:true});
 await expect(loader).toBeDisabled();
 await expect(loader).toHaveAttribute('title','An administrator or approver must load sample data');
});

test('analysts can analyze but cannot request order drafts',async({page})=>{
 await mockWorkspace(page,'analyst',true);
 await page.goto('/agent-dashboard');
 await expect(page.getByRole('button',{name:'Run analysis',exact:true})).toBeEnabled();
 await expect(page.getByRole('button',{name:'Run with draft creation',exact:true})).toBeDisabled();
 await expect(page.getByText('Analyst access: use Run analysis.',{exact:false})).toBeVisible();
});

test('draft-ready result survives refreshing products after the run',async({page})=>{
 await mockWorkspace(page,'admin',true);
 await page.goto('/agent-dashboard');
 await page.getByRole('button',{name:'Run with draft creation',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Purchase order draft ready',exact:true})).toBeVisible();
 await expect(page.getByText(/Order #123/)).toBeVisible();
 await expect(page.getByRole('link',{name:'Review purchase order',exact:true})).toBeVisible();
});
