// Read-only native acceptance. No model prompts, settings writes or microphone.
const {app,BrowserWindow}=require('electron');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),output=path.join(root,'data/test-results');
const origin=new URL(process.argv[2]);
if(origin.protocol!=='http:'||origin.hostname!=='127.0.0.1'||origin.pathname!=='/')throw Error('Expected loopback origin');
app.disableHardwareAcceleration();app.setPath('userData',path.join(output,'branding-preview-profile'));
let win;const checks=[];
async function waitFor(code){for(let i=0;i<200;i++){if(await win.webContents.executeJavaScript(code))return;await new Promise(r=>setTimeout(r,100));}throw Error('UI readiness timeout');}
function check(name,passed){checks.push({name,passed});if(!passed)throw Error(name);}
app.whenReady().then(async()=>{
 try{
  win=new BrowserWindow({show:false,width:1480,height:1000,webPreferences:{offscreen:true,sandbox:true,contextIsolation:true,nodeIntegration:false}});
  win.webContents.session.setPermissionRequestHandler((_wc,_p,done)=>done(false));
  await win.loadURL(origin.origin+'/overview');await waitFor(`!!document.querySelector('.indra-city-hero')`);
  check('hero-brand-is-indra-by-origo-labs',await win.webContents.executeJavaScript(`document.body.innerText.includes('ORIGO LABS')&&document.title.includes('Indra')`));
  await win.loadURL(origin.origin+'/guide');await waitFor(`document.body.textContent.includes('Indra guide')`);
  check('product-manual-is-bundled-and-offline',await win.webContents.executeJavaScript(`document.body.textContent.includes('Origo Labs')&&document.body.textContent.includes('Knowledge and project folders')&&!document.querySelector('iframe')`));
  check('no-old-team-or-upstream-product-label',await win.webContents.executeJavaScript(`!/(?:coders?bychance|Hermes Agent|Hermes dashboard)/i.test(document.body.innerText)`));
  await win.loadURL(origin.origin+'/chat');await waitFor(`!!document.querySelector('.indra-model-button:not(:disabled)')`);
  check('chat-and-model-picker-still-load',true);
 }catch(error){checks.push({name:error.message,passed:false});if(win)checks.push({diagnostic:await win.webContents.executeJavaScript(`({url:location.pathname,text:document.body.textContent.slice(0,1500)})`)});}
 finally{fs.writeFileSync(path.join(output,'branding-native-acceptance.json'),JSON.stringify(checks,null,2));app.exit(checks.every(c=>c.passed)?0:1);}
});
