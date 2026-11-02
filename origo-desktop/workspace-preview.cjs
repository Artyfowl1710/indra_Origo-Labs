// Native acceptance in an isolated renderer. Never records audio or sends a model prompt.
const {app,BrowserWindow}=require('electron');const fs=require('node:fs'),path=require('node:path');
app.disableHardwareAcceleration();
const root=path.resolve(__dirname,'..'),output=path.join(root,'data/test-results');
app.setPath('userData',path.join(output,'workspace-preview-profile'));
const origin=new URL(process.argv[2]);if(origin.protocol!=='http:'||origin.hostname!=='127.0.0.1'||!origin.port||origin.pathname!=='/')throw Error('Expected loopback origin');
let window;const rows=[];let latestPaint;
const fixture=path.join(root,'workspace/outputs/acceptance/Indra verification.md');
const evaluate=code=>window.webContents.executeJavaScript(code);
async function waitFor(code){for(let i=0;i<600;i++){if(await evaluate(code))return;await new Promise(r=>setTimeout(r,100));}throw Error('Timed out: '+code.slice(0,100));}
function check(name,passed){rows.push({name,passed});if(!passed)throw Error(name);}
async function capture(name){await new Promise(r=>setTimeout(r,500));const frame=latestPaint||await window.webContents.capturePage();fs.writeFileSync(path.join(output,name),frame.toPNG());}
async function theme(name,page){await window.loadURL(origin.origin+page);await waitFor(`!!document.querySelector('.stitch-runtime-cluster [aria-label="Switch theme"]')`);await evaluate(`document.querySelector('.stitch-runtime-cluster [aria-label="Switch theme"]').click()`);await waitFor(`!!document.querySelector('[data-theme-option="${name}"]')`);await evaluate(`document.querySelector('[data-theme-option="${name}"]').click()`);await waitFor(`document.documentElement.dataset.themeName===${JSON.stringify(name)}`);}
app.whenReady().then(async()=>{
 try{
  fs.mkdirSync(output,{recursive:true});fs.mkdirSync(path.dirname(fixture),{recursive:true});fs.writeFileSync(fixture,'# Verified artifact\n\nThis synthetic document checks the in-app preview.\n');
  window=new BrowserWindow({show:false,width:1480,height:1000,webPreferences:{offscreen:true,sandbox:true,contextIsolation:true,nodeIntegration:false,backgroundThrottling:false}});
  window.webContents.setFrameRate(20);window.webContents.on('paint',(_event,_dirty,frame)=>{latestPaint=frame;});
  window.webContents.session.setPermissionRequestHandler((_wc,_permission,callback)=>callback(false));
  await theme('nous-blue','/overview');
  await waitFor(`!!document.querySelector('.indra-city-video')&&document.querySelector('.indra-city-video').readyState>=2`);
  check('hero-video-local-muted-and-looping',await evaluate(`(()=>{const v=document.querySelector('.indra-city-video');return v.muted&&v.loop&&new URL(v.currentSrc).origin===location.origin})()`));
  await evaluate(`document.querySelector('[aria-label="Pause city animation"]')?.click()`);
  await waitFor(`document.querySelector('.indra-city-video').paused`);check('hero-pause-control',true);await capture('indra-blue-hero.png');
  await theme('ember','/overview');await waitFor(`!!document.querySelector('.indra-city-hero')`);await capture('indra-ember-hero.png');check('ember-theme-applied',true);
  await theme('default-large','/chat');
  await waitFor(`document.body.innerText.includes('Projects')&&!!document.querySelector('[aria-label="Open Conversation Mode"]:not(:disabled)')`);
  check('project-pane-visible',true);
  await waitFor(`Array.from(document.querySelectorAll('button')).some(b=>b.textContent.includes('Indra verification.md'))`);
  await evaluate(`Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('Indra verification.md')).click()`);
  await waitFor(`document.body.innerText.includes('Verified artifact')`);check('recent-artifact-opens-in-app-preview',true);await capture('indra-artifact-preview.png');
  await window.loadURL(origin.origin+'/chat');await waitFor(`!!document.querySelector('[aria-label="Open Conversation Mode"]:not(:disabled)')`);
  await evaluate(`(()=>{const b=document.querySelector('[aria-label="Open Conversation Mode"]');b.focus();b.click()})()`);
  await waitFor(`!!document.querySelector('.indra-voice-dialog')`);
  await waitFor(`document.querySelector('.indra-voice-dialog').contains(document.activeElement)`);
  check('voice-focus-contained',await evaluate(`document.querySelector('.indra-voice-dialog').contains(document.activeElement)`));
  await evaluate(`document.querySelector('.indra-voice-dialog [title="Voice Settings"]').click()`);
  await waitFor(`document.querySelector('.indra-voice-dialog').textContent.toLowerCase().includes('voice settings')`);await capture('indra-voice-teal.png');
  check('voice-controls-fit-viewport',await evaluate(`(()=>{const d=document.querySelector('.indra-voice-dialog>div').getBoundingClientRect();return d.width<=innerWidth&&d.height<=innerHeight})()`));
  await evaluate(`document.querySelector('.indra-voice-dialog [title^="Exit Conversation"]').click()`);
  await window.loadURL(origin.origin+'/files');await waitFor(`document.body.innerText.includes('Your documents, connected.')&&document.body.innerText.includes('MiniLM')`);check('knowledge-live-offline-model-status',true);await capture('indra-knowledge.png');
  await window.loadURL(origin.origin+'/logs');await waitFor(`document.body.innerText.includes('Signatures verified')`);check('signed-audit-verifies-in-native-ui',true);
  await window.loadURL(origin.origin+'/chat');await waitFor(`!!document.querySelector('.indra-model-button:not(:disabled)')`);await evaluate(`document.querySelector('.indra-model-button').click()`);
  await waitFor(`Array.from(document.querySelectorAll('.indra-model-picker .border-l-2')).some(e=>e.textContent.includes('origo-local'))`);
  await evaluate(`Array.from(document.querySelectorAll('.indra-model-picker .border-l-2')).find(e=>e.textContent.includes('origo-local')).click()`);
  await waitFor(`document.querySelector('.indra-model-picker').innerText.includes('Qwen2-VL OCR')`);check('both-local-models-advertised-with-roles',await evaluate(`document.querySelector('.indra-model-picker').innerText.includes('Coding agent')`));await capture('indra-local-models.png');
 }catch(error){rows.push({name:error.message,passed:false});if(window&&!window.isDestroyed())await capture('workspace-preview-failure.png');}
 finally{fs.writeFileSync(path.join(output,'workspace-native-acceptance.json'),JSON.stringify(rows,null,2));console.log(JSON.stringify(rows));try{fs.unlinkSync(fixture);}catch{}app.exit(rows.every(r=>r.passed)?0:1);}
});
