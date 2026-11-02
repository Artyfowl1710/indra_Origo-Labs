// Isolated renderer acceptance: fixture profile only, no paid model calls.
const {app,BrowserWindow}=require('electron');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),out=path.join(root,'data/test-results'),origin=new URL(process.argv[2]);
if(origin.hostname!=='127.0.0.1'||origin.protocol!=='http:'||origin.pathname!=='/')throw Error('Expected loopback origin');
app.disableHardwareAcceleration();app.setPath('userData',path.join(out,'objective-preview-profile'));
let win,latest;const checks=[];
const run=code=>win.webContents.executeJavaScript(code,true);
async function wait(code){for(let n=0;n<300;n++){if(await run(code))return;await new Promise(r=>setTimeout(r,100));}throw Error('Readiness timeout: '+code);}
function check(name,passed,detail){checks.push({name,passed,...(detail?{detail}:{})});if(!passed)throw Error(name);}
async function screenshot(name){await run(`new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`);await new Promise(resolve=>setTimeout(resolve,600));if(!latest)throw Error('No renderer paint received');fs.writeFileSync(path.join(out,name),latest.toPNG());}
const headers=`{'X-Hermes-Session-Token':window.__HERMES_SESSION_TOKEN__,'Content-Type':'application/json'}`;
async function theme(name){await run(`fetch('/api/dashboard/theme',{method:'PUT',headers:${headers},body:JSON.stringify({name:${JSON.stringify(name)}})})`);await run(`localStorage.setItem('hermes-dashboard-theme',${JSON.stringify(name)})`);}
const contrast=`(element)=>{
 const rgba=s=>{const n=s.match(/[\\d.]+/g)?.map(Number)??[0,0,0];return [n[0]/255,n[1]/255,n[2]/255,n[3]??1];};
 const mix=(front,back)=>{const a=front[3]+back[3]*(1-front[3]);return [0,1,2].map(i=>(front[i]*front[3]+back[i]*back[3]*(1-front[3]))/(a||1)).concat(a);};
 let bg=[0,0,0,0];for(let node=element;node&&bg[3]<.999;node=node.parentElement)bg=mix(bg,rgba(getComputedStyle(node).backgroundColor));bg=mix(bg,[1,1,1,1]);
 const fg=mix(rgba(getComputedStyle(element).color),bg),lum=c=>c.slice(0,3).reduce((v,x,i)=>v+[.2126,.7152,.0722][i]*(x<=.04045?x/12.92:((x+.055)/1.055)**2.4),0),a=lum(fg),b=lum(bg);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
}`;
app.whenReady().then(async()=>{
 try{
  fs.mkdirSync(out,{recursive:true});win=new BrowserWindow({show:false,width:1480,height:1000,webPreferences:{offscreen:true,backgroundThrottling:false,nodeIntegration:false,contextIsolation:true,sandbox:true}});
  win.webContents.on('paint',(_event,_rect,frame)=>latest=frame);
  win.webContents.session.setPermissionRequestHandler((_w,_p,done)=>done(false));
  await win.loadURL(origin.origin+'/chat');await wait(`!!document.querySelector('.indra-model-button:not(:disabled)')`);
  await run(`(()=>{const input=document.querySelector('textarea[aria-label="Message INDRA"]');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(input,'/goal status');input.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await run(`document.querySelector('textarea[aria-label="Message INDRA"]').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))`);
  await wait(`document.querySelector('.indra-goal-status')?.textContent.includes('No active goal')`);
  check('chat-goal-status-uses-persistent-core-control-without-model-call',true);
  await run(`document.querySelector('.indra-model-button').click()`);await wait(`!!document.querySelector('.indra-model-picker')`);
  await run(`Array.from(document.querySelectorAll('.indra-model-picker button')).find(b=>b.textContent.includes('Add API key')).click()`);
  await run(`Array.from(document.querySelectorAll('.indra-model-connect-form button')).find(b=>b.textContent.includes('Use Baseten')).click()`);
  check('model-picker-baseten-hackathon-preset',await run(`Array.from(document.querySelectorAll('.indra-model-connect-form input')).some(e=>e.value==='meta-models/muse-spark-open-1026')`));
  for(const name of ['default','midnight','nous-blue','ember']){
   await theme(name);await win.loadURL(origin.origin+'/chat');await wait(`document.documentElement.dataset.themeName===${JSON.stringify(name)}&&!!document.querySelector('[aria-label="Open Conversation Mode"]:not(:disabled)')`);
   check(name+'-record-panel-hidden-in-chat',await run(`!document.querySelector('.indra-conversation-record')`));
   const icon=await run(`(()=>{const e=document.querySelector('.indra-composer-input>button>svg'),s=getComputedStyle(e);return {stroke:s.stroke,color:s.color,visible:s.display!=='none'&&s.visibility!=='hidden',contrast:(${contrast})(e)};})()`);
   check(name+'-send-arrow-visible-with-contrast',icon.visible&&icon.stroke!=='none'&&icon.contrast>=3,icon);
   await run(`document.querySelector('[title="Open Server & AI Settings"]').click()`);await wait(`!!document.querySelector('.indra-settings-dialog')`);
   await run(`Array.from(document.querySelectorAll('.indra-settings-dialog button')).find(b=>b.textContent.trim()==='Conversation & export').click()`);await wait(`!!document.querySelector('.indra-conversation-record')`);
   const record=await run(`(${contrast})(document.querySelector('.indra-conversation-record summary'))`);check(name+'-settings-record-contrast',record>=4.5,{contrast:record});
   await screenshot('objective-settings-'+name+'.png');
   await win.loadURL(origin.origin+'/sandbox');await wait(`document.body.textContent.includes('Local Host (Native)')`);
   await wait(`!document.body.textContent.includes('Loading execution environment…')`);
   const values=await run(`Array.from(document.querySelectorAll('.indra-product-page strong')).filter(e=>['Local Host (Native)','Docker Sandbox Container'].includes(e.textContent.trim())).map(e=>({label:e.textContent,contrast:(${contrast})(e)}))`);
   check(name+'-sandbox-card-text-contrast',values.length===2&&values.every(v=>v.contrast>=4.5),values);
   check(name+'-docker-switch-reflects-running-engine',await run(`!Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('Switch to Docker Sandbox'))?.disabled`));
   await screenshot('objective-sandbox-'+name+'.png');
  }
  await theme('default');
 }catch(error){checks.push({name:String(error.message),passed:false});}
 finally{fs.writeFileSync(path.join(out,'product-objective-native-acceptance.json'),JSON.stringify(checks,null,2));app.exit(checks.every(c=>c.passed)?0:1);}
});
