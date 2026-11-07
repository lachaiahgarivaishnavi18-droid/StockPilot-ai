import {test,expect} from '@playwright/test';
test('demo login, forecast, agent draft and human approval',async({page,request})=>{
 // Select a product that still needs replenishment: prior test approvals count
 // as confirmed incoming stock and must not be ignored on repeated runs.
 const login=await request.post('/api/auth/login',{data:{email:'demo@stockpilot.local',password:'StockPilot-demo-2026!'}});
 expect(login.ok()).toBeTruthy();
 const auth=await login.json();
 const plans=await request.get('/api/replenishment/recommendations',{headers:{Authorization:'Bearer '+auth.access_token}});
 const recommendations=await plans.json();
 const candidate=recommendations.find((r:any)=>r.quantity>0&&r.available+r.incoming<r.reorder_point*.5)||recommendations.find((r:any)=>r.quantity>0);
 expect(candidate,'Use a demo database with a product requiring replenishment').toBeTruthy();
 await page.goto('/');
 await page.getByLabel('Email address').fill('demo@stockpilot.local');
 await page.getByLabel('Password',{exact:true}).fill('StockPilot-demo-2026!');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Executive Overview',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Generate forecast',exact:true}).click();
 await expect(page.getByText(/Held-out MAE/)).toBeVisible({timeout:120000});
 await page.goto('/agent-dashboard');
 await page.getByLabel('Selected product').selectOption(String(candidate.product_id));
 await page.getByRole('button',{name:'Run with draft creation'}).click();
 await expect(page.getByRole('status').filter({hasText:/Workflow finished/})).toBeVisible({timeout:120000});
 await page.goto('/purchase-order-management');
 await page.locator('tbody tr').first().click();
 await page.getByRole('checkbox').check();
 await page.getByRole('button',{name:'Approve local purchase order'}).click();
 await expect(page.getByRole('status').filter({hasText:'Human approval recorded'})).toBeVisible();
});
