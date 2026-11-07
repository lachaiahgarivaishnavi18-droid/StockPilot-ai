import {spawnSync} from 'node:child_process';
function run(command,args,cwd){
 const result=spawnSync(command,args,{cwd,stdio:'inherit',shell:process.platform==='win32'});
 if(result.status!==0)process.exit(result.status||1);
}
run('npm',['install','--no-audit','--no-fund'],'frontend');
run('npm',['run','build'],'frontend');
run('python',['deploy_init.py'],'backend');
