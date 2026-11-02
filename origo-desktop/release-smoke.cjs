// Opt-in isolated release verification. No approval or authentication bypass.
const {app}=require('electron');
const fs=require('node:fs');
const path=require('node:path');
if(!process.env.ORIGO_HOME || !process.env.ORIGO_DESKTOP_USER_DATA || !process.env.ORIGO_SMOKE_REPORT)throw Error('Smoke tests require explicit isolated paths.');
const report=process.env.ORIGO_SMOKE_REPORT;
const timeout=setTimeout(()=>{fs.writeFileSync(report,JSON.stringify({ok:false,error:'startup timeout'}));app.exit(1);},120000);
app.whenReady().then(async()=>{
  const result=await require('./main.cjs').start({show:false});
  await new Promise(resolve=>setTimeout(resolve,2000));
  const page=await result.window.webContents.executeJavaScript('({title:document.title,text:document.body.innerText.slice(0,1600),rootChildren:document.getElementById("root")?.childElementCount || 0})');
  const api=await result.window.webContents.executeJavaScript(`Promise.all(['/api/status','/api/sessions?limit=2','/api/model/info'].map(async url=>{const r=await fetch(url,{headers:{'X-Hermes-Session-Token':window.__HERMES_SESSION_TOKEN__||''}});return {url,status:r.status,problem:r.ok?null:(await r.text()).slice(0,500)}}))`);
  const toolProbe=require('node:child_process').spawnSync('python',['-c','import sys;print(sys.executable)'],{encoding:'utf8',windowsHide:true});
  const toolPythonBundled=toolProbe.status===0 && path.resolve(toolProbe.stdout.trim()).toLowerCase()===path.resolve(__dirname,'../runtime/python/python.exe').toLowerCase();
  const probeDir=fs.mkdtempSync(path.join(require('node:os').tmpdir(),'indra-python-probe-'));
  let toolProjectImports=false;
  try{
    fs.writeFileSync(path.join(probeDir,'indra_example_module.py'),'value=73\n');
    fs.writeFileSync(path.join(probeDir,'probe.py'),'import indra_example_module;print(indra_example_module.value)\n');
    const run=require('node:child_process').spawnSync;
    const a=run('python',['probe.py'],{cwd:probeDir,encoding:'utf8',windowsHide:true});
    const b=run('python',['-c','import indra_example_module;print(indra_example_module.value)'],{cwd:probeDir,encoding:'utf8',windowsHide:true});
    toolProjectImports=a.status===0 && a.stdout.trim()==='73' && b.status===0 && b.stdout.trim()==='73';
  }finally{
    const tempRoot=path.resolve(require('node:os').tmpdir())+path.sep;
    if(!path.resolve(probeDir).startsWith(tempRoot) || !path.basename(probeDir).startsWith('indra-python-probe-'))throw Error('Unexpected probe cleanup path');
    fs.rmSync(probeDir,{recursive:true,force:true});
  }
  const ok=page.rootChildren>0 && /indra/i.test(page.text) && api.every(r=>r.status===200) && toolPythonBundled && toolProjectImports;
  fs.writeFileSync(report,JSON.stringify({ok,packaged:app.isPackaged,timings:result.timings,page,api,toolPythonBundled,toolProjectImports},null,2));
  if(process.env.ORIGO_SMOKE_SCREENSHOT){const capture=await result.window.webContents.capturePage();fs.writeFileSync(process.env.ORIGO_SMOKE_SCREENSHOT,capture.toPNG());}
  clearTimeout(timeout);app.quit();
}).catch(error=>{clearTimeout(timeout);fs.writeFileSync(report,JSON.stringify({ok:false,error:error.stack},null,2));app.quit();});
