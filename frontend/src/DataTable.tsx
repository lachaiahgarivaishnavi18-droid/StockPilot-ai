import React,{useState} from 'react';
import {Search} from 'lucide-react';
const badge=(s:string)=><span className={'badge '+s}>{s?.replaceAll('_',' ')}</span>;
export function DataTable({rows,columns,onRow}:{rows:any[],columns:[string,string][],onRow?:(r:any)=>void}){
 const [search,setSearch]=useState(''),[page,setPage]=useState(1);
 const filtered=rows.filter(r=>JSON.stringify(r).toLowerCase().includes(search.toLowerCase()));
 const pageRows=filtered.slice((page-1)*10,page*10);
 return <><div className="table-tools"><span>{filtered.length} records</span><label className="search"><Search size={15}/><input aria-label="Search records" placeholder="Search records…" value={search} onChange={e=>{setSearch(e.target.value);setPage(1)}}/></label></div><div className="table-scroll"><table><thead><tr>{columns.map(([k,v])=><th key={k}>{v}</th>)}</tr></thead><tbody>{pageRows.map((r,i)=><tr key={r.id||i} onClick={()=>onRow?.(r)} className={onRow?'clickable':''}>{columns.map(([k])=><td key={k}>{k==='status'?badge(r[k]):typeof r[k]==='number'?Number(r[k].toFixed(2)).toLocaleString():String(r[k]??'—')}</td>)}</tr>)}</tbody></table>{!filtered.length&&<div className="empty">No records yet. Load the sample dataset or import your data.</div>}</div><div className="pagination"><button disabled={page===1} onClick={()=>setPage(page-1)}>Previous</button><span>Page {page} of {Math.max(1,Math.ceil(filtered.length/10))}</span><button disabled={page*10>=filtered.length} onClick={()=>setPage(page+1)}>Next</button></div></>
}
