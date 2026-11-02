// Read-only acceptance in an isolated native renderer; no model or key changes.
const {app,BrowserWindow}=require('electron');
const fs=require('node:fs'),path=require('node:path');
const origin=new URL(process.argv[2]);
if(origin.protocol!=='http:'||origin.hostname!=='127.0.0.1'||!origin.port||origin.pathname!=='/'||origin.search||origin.hash)throw Error('Expected loopback origin');
const output=path.resolve(__dirname,'../data/test-results');
app.setPath('userData',path.join(output,'media-preview-profile'));
let window;const rows=[];
const evaluate=code=>window.webContents.executeJavaScript(code);
async function waitFor(code){for(let i=0;i<600;i++){if(await evaluate(code))return;await new Promise(r=>setTimeout(r,100));}throw Error('Renderer timeout');}
function check(test,passed){rows.push({test,passed});if(!passed)throw Error(test);}
async function filter(value){await evaluate(`(()=>{const e=document.getElementById('indra-model-picker-filter');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));})()`);}
app.whenReady().then(async()=>{
 try{
  fs.mkdirSync(output,{recursive:true});
  window=new BrowserWindow({show:false,width:1550,height:1000,webPreferences:{sandbox:true,contextIsolation:true,nodeIntegration:false,backgroundThrottling:false}});
  await window.loadURL(origin.origin+'/system');
  await waitFor(`!!document.querySelector('#cred-provider option[value="gemini"]')`);
  check('google-in-key-provider-dropdown',true);
  check('self-hosted-form-and-optional-key',await evaluate(`document.body.innerText.includes('Connect your own model server')&&document.body.innerText.includes('API key (optional)')`));
  await window.loadURL(origin.origin+'/chat');
  await waitFor(`!!document.querySelector('.indra-model-button:not(:disabled)')`);
  await evaluate(`document.querySelector('.indra-model-button').click()`);
  await waitFor(`Array.from(document.querySelectorAll('.indra-model-picker .border-l-2')).some(e=>e.textContent.includes('gemini ·'))`);
  await evaluate(`Array.from(document.querySelectorAll('.indra-model-picker .border-l-2')).find(e=>e.textContent.includes('gemini ·')).click()`);
  await filter('gemini-3.8-flash');
  await waitFor(`document.querySelector('.indra-model-picker').innerText.includes('gemini-3.8-flash')&&document.querySelector('.indra-model-picker').innerText.includes('Multimodal')`);
  check('gemini-media-labels',await evaluate(`['Image','Video','Audio'].every(s=>document.querySelector('.indra-model-picker').innerText.includes(s))`));
  await filter('gemini-3.8-flash-tts');
  await waitFor(`document.querySelector('.indra-model-picker').innerText.includes('gemini-3.8-flash-tts')&&document.querySelector('.indra-model-picker').innerText.includes('speech')`);
  check('specialist-label-visible',true);
  await new Promise(r=>setTimeout(r,300));
  fs.writeFileSync(path.join(output,'google-media-picker.png'),(await window.webContents.capturePage()).toPNG());
  await evaluate(`(()=>{const e=Array.from(document.querySelectorAll('.indra-model-picker span')).find(e=>e.textContent==='gemini-3.8-flash-tts');e?.dispatchEvent(new MouseEvent('dblclick',{bubbles:true}));})()`);
  await waitFor(`document.body.innerText.includes('This is a specialist API model')`);
  check('specialist-cannot-accidentally-become-chat-model',true);
 }catch(error){rows.push({test:error.message,passed:false});if(window)fs.writeFileSync(path.join(output,'media-preview-failure.png'),(await window.webContents.capturePage()).toPNG());}
 finally{fs.writeFileSync(path.join(output,'media-renderer.json'),JSON.stringify(rows,null,2));console.log(JSON.stringify(rows));app.exit(rows.every(r=>r.passed)?0:1);}
});
