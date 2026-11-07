const localHost=['localhost','127.0.0.1','::1'].includes(window.location.hostname);
export async function api(path:string,body?:unknown,method?:string):Promise<any>{
 const token=sessionStorage.getItem('stockpilot-token');
 let response:Response;
 try {
 response=await fetch('/api'+path,{method:method||(body?'POST':'GET'),headers:{...(token?{Authorization:'Bearer '+token}:{}),...(body instanceof FormData?{}:{'Content-Type':'application/json'})},body:body instanceof FormData?body:body?JSON.stringify(body):undefined});
 } catch { throw new Error(localHost?'Cannot connect to StockPilot. Start the local servers with .\\scripts\\start.ps1, then refresh this page.':'Cannot connect to StockPilot. Refresh the page or try again shortly.') }
 const content=await response.text();
 let data:any;
 try { data=JSON.parse(content) } catch { throw new Error(localHost?'The StockPilot API is unavailable. Run .\\scripts\\start.ps1 and check the .logs folder if it cannot start.':'The StockPilot API is temporarily unavailable. Please try again shortly.') }
 if(response.status===401){sessionStorage.removeItem('stockpilot-token');window.dispatchEvent(new Event('stockpilot-session-expired'))}
 if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
 return data;
}
export function download(data:unknown,name:string){const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download=name;link.click();URL.revokeObjectURL(url)}
