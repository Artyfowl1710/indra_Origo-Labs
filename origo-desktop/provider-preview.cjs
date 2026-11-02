// Read-only native model-picker acceptance; never switches models or sends prompts.
const {app,BrowserWindow}=require('electron');
const fs=require('node:fs'),path=require('node:path');
const url=new URL(process.argv[2]);
if(url.protocol!=='http:'||url.hostname!=='127.0.0.1'||!url.port||url.pathname!=='/'||url.search||url.hash||url.username||url.password)throw Error('Expected loopback origin');
const output=path.resolve(__dirname,'../data/test-results');
app.setPath('userData',path.join(output,'provider-preview-profile'));
const rows=[];let window,refreshObserved=false;
async function evaluate(code){return window.webContents.executeJavaScript(code);}
async function waitFor(code){for(let i=0;i<600;i++){if(await evaluate(code))return;await new Promise(r=>setTimeout(r,100));}throw Error('Renderer condition timed out: '+code.slice(0,180));}
function record(test,passed){rows.push({test,passed});if(!passed)throw Error(test);}
const modelVisible=id=>`Array.from(document.querySelectorAll('span')).some(e=>e.textContent===${JSON.stringify(id)})`;
async function filter(value){
  await evaluate(`(()=>{const input=document.getElementById('indra-model-picker-filter');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,${JSON.stringify(value)});input.dispatchEvent(new Event('input',{bubbles:true}));})()`);
}
app.whenReady().then(async()=>{
 try{
  fs.mkdirSync(output,{recursive:true});
  window=new BrowserWindow({show:false,width:1400,height:950,webPreferences:{sandbox:true,contextIsolation:true,nodeIntegration:false,backgroundThrottling:false}});
  window.webContents.session.webRequest.onBeforeRequest({urls:[url.origin+'/api/model/options*']},(details,callback)=>{
    if(new URL(details.url).searchParams.get('refresh')==='1')refreshObserved=true;
    callback({});
  });
  await window.loadURL(url.origin+'/chat');
  await waitFor(`!!document.querySelector('.indra-model-button:not(:disabled)')`);
  await evaluate(`document.querySelector('.indra-model-button').click()`);
  await waitFor(`Array.from(document.querySelectorAll('.border-l-2')).some(e=>e.textContent.includes('openrouter ·'))`);
  await evaluate(`Array.from(document.querySelectorAll('.border-l-2')).find(e=>e.textContent.includes('openrouter ·')).click()`);
  await filter('nemotron-3.5-super-vl');
  await waitFor(modelVisible('nvidia/nemotron-3.5-super-vl:free'));
  record('nemotron-paid-and-free-both-listed',await evaluate(modelVisible('nvidia/nemotron-3.5-super-vl')));
  record('nemotron-image-video-badges',await evaluate(`document.body.innerText.includes('Image')&&document.body.innerText.includes('Video')`));
  await evaluate(`document.querySelector('label input[type="checkbox"]').click()`);
  await waitFor(`!(${modelVisible('nvidia/nemotron-3.5-super-vl')})`);
  record('free-filter-keeps-free-variant',await evaluate(modelVisible('nvidia/nemotron-3.5-super-vl:free')));
  await filter('dots');
  await waitFor(modelVisible('dots-studio/dots-3-note-preview:free'));
  record('dots-free-present',true);
  await new Promise(r=>setTimeout(r,250));
  fs.writeFileSync(path.join(output,'provider-dots-free.png'),(await window.webContents.capturePage()).toPNG());
  await evaluate(`Array.from(document.querySelectorAll('button')).find(e=>e.textContent.trim()==='Refresh Models').click()`);
  for(let i=0;i<50&&!refreshObserved;i++)await new Promise(r=>setTimeout(r,100));
  record('refresh-reaches-api-with-refresh-flag',refreshObserved);
  await waitFor(`Array.from(document.querySelectorAll('button')).some(e=>e.textContent.trim()==='Refresh Models'&&!e.disabled)`);
  await filter('');
  await evaluate(`Array.from(document.querySelectorAll('.border-l-2')).find(e=>e.textContent.includes('opencode-free ·')).click()`);
  await waitFor(`document.body.innerText.includes('OpenCode restricts free-tier chat')`);
  record('opencode-access-restriction-visible',true);
 }catch(error){
  rows.push({test:error.message,passed:false});
  if(window&&!window.isDestroyed())fs.writeFileSync(path.join(output,'provider-preview-failure.png'),(await window.webContents.capturePage()).toPNG());
 }
 finally{
  fs.writeFileSync(path.join(output,'provider-renderer.json'),JSON.stringify(rows,null,2));
  console.log(JSON.stringify(rows));app.exit(rows.length===6&&rows.every(r=>r.passed)?0:1);
 }
});
