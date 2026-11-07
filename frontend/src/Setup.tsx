import React,{useState} from 'react';
import {Package,ArrowRight} from 'lucide-react';
import {api} from './api';

export function Setup({token,onLogin}:{token:string,onLogin:()=>void}){
 const [error,setError]=useState(''),[busy,setBusy]=useState(false);
 return <div className="login"><div className="login-story"><div className="brand"><Package/>StockPilot <span>AI</span></div><div><span className="eyebrow">YOUR CLOUD WORKSPACE</span><h1>Ready for<br/>your first flight.</h1><p>Create your administrator account to manage products, load demonstration data, and approve replenishment orders.</p></div><small>This setup link works only until the first administrator is created.</small></div><form onSubmit={async event=>{
  event.preventDefault();setBusy(true);setError('');
  const values=new FormData(event.currentTarget);
  try{
   const result=await api('/auth/bootstrap',{name:String(values.get('name')),email:String(values.get('email')),password:String(values.get('password')),setup_token:token});
   sessionStorage.setItem('stockpilot-token',result.access_token);
   history.replaceState(null,'',location.pathname);onLogin();
  }catch(exc){setError(String(exc))}finally{setBusy(false)}
 }}><span className="eyebrow">ONE-TIME ADMINISTRATOR SETUP</span><h2>Make this workspace yours</h2><label>Your name<input name="name" required maxLength={100}/></label><label>Email address<input name="email" type="email" required/></label><label>Password<input name="password" type="password" minLength={10} maxLength={128} required autoComplete="new-password"/></label>{error&&<p className="error" role="alert">{error}</p>}<button className="primary" disabled={busy}>{busy?'Creating account…':'Create administrator account'}<ArrowRight size={16}/></button><small>Choose your own password. Local demo credentials are not enabled on this hosted deployment.</small></form></div>
}
