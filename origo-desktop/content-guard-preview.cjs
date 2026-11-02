// Isolated native UI probe: one pre-authorized fixture operation, not a human trial.
const {app,BrowserWindow}=require('electron'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),out=path.join(root,'data/test-results');
fs.writeFileSync(path.join(out,'content-guard-preview-started.json'),JSON.stringify({started:true,argument_count:process.argv.length}));
const [originText,chat,requestId]=process.argv.slice(2).filter(v=>v!=='--'),origin=new URL(originText);
if(origin.hostname!=='127.0.0.1'||origin.protocol!=='http:'||origin.pathname!=='/'||!chat||!requestId)throw Error('Expected fixture origin, chat and request');
app.disableHardwareAcceleration();app.setPath('userData',path.join(out,'content-guard-preview-profile'));
let win,latest;const checks=[];const run=code=>win.webContents.executeJavaScript(code,true);
async function wait(code){for(let n=0;n<300;n++){if(await run(code))return;await new Promise(r=>setTimeout(r,100));}throw Error('Timed out: '+code);}
function check(name,passed){checks.push({name,passed});if(!passed)throw Error(name);}
const audit=`(async()=>{const r=await fetch('/api/indra/workspace/audit',{headers:{'X-Hermes-Session-Token':window.__HERMES_SESSION_TOKEN__}});if(!r.ok)throw Error('Audit unavailable');return r.json();})()`;
app.whenReady().then(async()=>{
 try{
  win=new BrowserWindow({show:false,width:1480,height:1050,webPreferences:{offscreen:true,backgroundThrottling:false,nodeIntegration:false,contextIsolation:true,sandbox:true}});win.webContents.on('paint',(_e,_r,frame)=>latest=frame);
  await win.loadURL(origin.origin+'/chat?resume='+encodeURIComponent(chat));
  await wait(`!!document.querySelector('.indra-action-card--approval')`);
  check('review-is-bound-to-preauthorized-fixture-request',await run(`document.querySelector('.indra-action-card--approval').dataset.approvalRequestId===${JSON.stringify(requestId)}`));
  check('resumed-fixture-chat-hydrates-pending-review',await run(`document.querySelector('.indra-action-card--approval').textContent.includes('untrusted content')`));
  check('review-offers-once-and-deny-without-session-scope',await run(`(()=>{const labels=Array.from(document.querySelectorAll('.indra-action-card--approval button')).map(b=>b.textContent.trim());return labels.length===2&&labels.some(t=>t.includes('Approve (Once)'))&&labels.some(t=>t.includes('Deny'))&&!labels.some(t=>t.includes('Always'));})()`));
  const before=await run(audit);const head=Math.max(0,...before.events.map(e=>e.seq));
  await run(`document.querySelector('.indra-action-card--approval').scrollIntoView({block:'center'});new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`);await new Promise(r=>setTimeout(r,600));if(latest)fs.writeFileSync(path.join(out,'content-guard-review.png'),latest.toPNG());
  await run(`Array.from(document.querySelectorAll('.indra-action-card--approval button')).find(b=>b.textContent.includes('Approve (Once)')).click()`);
  await wait(`(async()=>{const a=await ${audit};return a.events.some(e=>e.seq>${head}&&e.kind==='security.human_review_answered'&&e.payload.choice==='once');})()`);
  check('native-once-choice-reaches-signed-audit',true);
 }catch(error){checks.push({name:error.message,passed:false});}
 finally{fs.writeFileSync(path.join(out,'content-guard-native-acceptance.json'),JSON.stringify(checks,null,2));app.exit(checks.every(c=>c.passed)?0:1);}
});
