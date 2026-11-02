// Real renderer + authenticated goal RPCs. Save drafts only; no model calls.
const {app,BrowserWindow}=require('electron'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),out=path.join(root,'data/test-results'),origin=new URL(process.argv[2]);
if(origin.hostname!=='127.0.0.1'||origin.protocol!=='http:'||origin.pathname!=='/')throw Error('Expected loopback origin');
app.disableHardwareAcceleration();app.setPath('userData',path.join(out,'goal-workflow-preview-profile'));
let win,latest;const checks=[];const run=code=>win.webContents.executeJavaScript(code,true);
async function wait(code){for(let n=0;n<300;n++){if(await run(code))return;await new Promise(r=>setTimeout(r,100));}throw Error('Timed out: '+code);}
function check(name,passed){checks.push({name,passed});if(!passed)throw Error(name);}
async function fill(selector,value){await run(`(()=>{const input=document.querySelector(${JSON.stringify(selector)});Object.getOwnPropertyDescriptor(input.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set.call(input,${JSON.stringify(value)});input.dispatchEvent(new Event('input',{bubbles:true}));})()`);}
const button=text=>`Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()===${JSON.stringify(text)})`;
app.whenReady().then(async()=>{
 try{
  win=new BrowserWindow({show:false,width:1480,height:1000,webPreferences:{offscreen:true,backgroundThrottling:false,nodeIntegration:false,contextIsolation:true,sandbox:true}});win.webContents.on('paint',(_e,_r,frame)=>latest=frame);
  await win.loadURL(origin.origin+'/chat');await wait(`!!${button('Set project goal')}&&!${button('Set project goal')}.disabled`);
  await run(`${button('Set project goal')}.click()`);await wait(`!!document.querySelector('.indra-goal-dialog')`);
  await fill('[aria-label="Goal objective"]','Build a verified fixture project');await fill('[aria-label="Goal verification"]','All fixture tests pass and the output is readable.');
  await run(`${button('Add check')}.click()`);await fill('[aria-label="Quality check 1"]','python -m pytest -q');
  await new Promise(r=>setTimeout(r,600));if(latest)fs.writeFileSync(path.join(out,'goal-editor.png'),latest.toPNG());
  await run(`${button('Save goal')}.click()`);await wait(`!document.querySelector('.indra-goal-dialog')&&document.querySelector('.indra-goal-panel')?.textContent.includes('Build a verified fixture project')`);
  check('goal-editor-saves-paused-objective-with-check',await run(`document.querySelector('.indra-goal-panel').textContent.includes('paused')&&document.querySelector('.indra-goal-panel').textContent.includes('python -m pytest -q')`));
  const stored=await run(`(async()=>{const response=await fetch('/api/sessions?limit=100&order=recent',{headers:{'X-Hermes-Session-Token':window.__HERMES_SESSION_TOKEN__}});const body=await response.json();return body.sessions.find(s=>s.title?.startsWith('Goal · Build a verified fixture project'))?.id;})()`);
  check('goal-draft-is-discoverable-in-sessions',!!stored);
  await win.loadURL(origin.origin+'/chat?resume='+encodeURIComponent(stored));await wait(`document.querySelector('.indra-goal-panel')?.textContent.includes('Build a verified fixture project')`);
  check('goal-contract-and-check-survive-resume',await run(`document.querySelector('.indra-goal-panel').textContent.includes('python -m pytest -q')&&!!${button('Start goal')}`));
  await run(`${button('Edit goal')}.click()`);await wait(`!!document.querySelector('.indra-goal-dialog')`);
  check('goal-editor-restores-completion-evidence',await run(`document.querySelector('[aria-label="Goal verification"]').value==='All fixture tests pass and the output is readable.'`));
  await run(`document.querySelector('[aria-label="Remove check 1"]').click()`);await run(`${button('Save goal')}.click()`);await wait(`!document.querySelector('.indra-goal-dialog')`);
  check('editing-removes-check-without-running-model',await run(`!document.querySelector('.indra-goal-panel').textContent.includes('python -m pytest -q')`));
  await new Promise(r=>setTimeout(r,600));if(latest)fs.writeFileSync(path.join(out,'goal-saved.png'),latest.toPNG());
 }catch(error){checks.push({name:error.message,passed:false});if(win)checks.push({diagnostic:await run(`({panel:document.querySelector('.indra-goal-panel')?.textContent,dialog:document.querySelector('.indra-goal-dialog')?.textContent})`)});}
 finally{fs.writeFileSync(path.join(out,'goal-workflow-native-acceptance.json'),JSON.stringify(checks,null,2));app.exit(checks.every(c=>c.passed)?0:1);}
});
