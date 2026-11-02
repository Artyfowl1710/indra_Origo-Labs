const {test}=require('node:test');
const assert=require('node:assert/strict');
const {authorizeSetup}=require('../origo-desktop/phone-window.cjs');

function fixture(){
  const url='file:///C:/Origo/phone-setup.html';
  const frame={url};const contents={mainFrame:frame};
  return {url,window:{isDestroyed:()=>false,webContents:contents},event:{sender:contents,senderFrame:frame}};
}
test('native setup main frame can configure phone sharing',()=>{
  const f=fixture();assert.doesNotThrow(()=>authorizeSetup(f.event,f.window,f.url));
});
test('remote dashboard cannot invoke native settings even with a matching URL string',()=>{
  const f=fixture();assert.throws(()=>authorizeSetup({...f.event,sender:{}},f.window,f.url));
});
test('a subframe cannot impersonate the setup main frame',()=>{
  const f=fixture();assert.throws(()=>authorizeSetup({...f.event,senderFrame:{url:f.url}},f.window,f.url));
});
test('navigation away from the bundled setup document revokes access',()=>{
  const f=fixture();f.event.senderFrame.url='https://external.example/phone-setup.html';
  assert.throws(()=>authorizeSetup(f.event,f.window,f.url));
});
test('closing the setup window revokes its capability',()=>{
  const f=fixture();f.window.isDestroyed=()=>true;
  assert.throws(()=>authorizeSetup(f.event,f.window,f.url));
  assert.throws(()=>authorizeSetup(f.event,null,f.url));
});
