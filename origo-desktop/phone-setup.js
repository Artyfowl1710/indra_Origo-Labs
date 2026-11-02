const form=document.getElementById('pairing-form');
const status=document.getElementById('share-status');
const message=document.getElementById('message');
const save=document.getElementById('save');
const disable=document.getElementById('disable');
function busy(value){save.disabled=value;disable.disabled=value;}
async function initialize(){
  try {
    const {settings,share}=await window.origoPhone.read();
    if(settings){
      document.getElementById('endpoint').value=settings.endpoint;
      document.getElementById('username').value=settings.username;
      document.getElementById('port').value=settings.port;
      disable.hidden=!settings.enabled;
    }
    status.textContent=share.message;
  } catch {status.textContent='Phone settings could not be read. Check the profile permissions.';}
}
form.addEventListener('submit',async event=>{
  event.preventDefault();busy(true);message.textContent='Saving protected settings…';
  try {
    await window.origoPhone.save({endpoint:document.getElementById('endpoint').value,
      username:document.getElementById('username').value,password:document.getElementById('password').value,
      port:Number(document.getElementById('port').value)});
    message.textContent='Restarting Origo. Sign in on this PC and your phone using the password you just set.';
  } catch {message.textContent='Could not save. Check the HTTPS address, password length and local port.';busy(false);}
  finally{document.getElementById('password').value='';}
});
disable.addEventListener('click',async()=>{
  busy(true);
  try {await window.origoPhone.disable();message.textContent='Restarting with phone sharing stopped. Workstation sign-in stays enabled.';}
  catch {message.textContent='Could not stop sharing. Settings were not confirmed; keep Origo open and retry.';busy(false);}
});
initialize();
const refresh=setInterval(async()=>{
  try{const share=await window.origoPhone.status();status.textContent=share.message;}catch{}
},3000);
window.addEventListener('beforeunload',()=>clearInterval(refresh));
