const {test}=require('node:test');
const assert=require('node:assert/strict');
const {startOptionalLocalRouting,localStartupNotice,waitForService}=require('./local-startup.cjs');
const http=require('node:http');

test('missing assets preserve workspace availability without starting an engine',async()=>{
  let calls=0;
  const result=await startOptionalLocalRouting({
    enabled:false,issue:'models-missing',start:async()=>{calls++;},stop:async()=>{calls++;},
  });
  assert.deepEqual(result,{ready:false,issue:'models-missing'});
  assert.equal(calls,0);
  assert.match(localStartupNotice(result.issue).detail,/saved model selection is unchanged/);
});

test('engine startup failure cleans up before continuing and hides raw errors',async()=>{
  const actions=[];
  const result=await startOptionalLocalRouting({
    enabled:true,start:async()=>{actions.push('start');throw Error('private fixture detail');},
    stop:async()=>{actions.push('stop');},
  });
  assert.deepEqual(actions,['start','stop']);
  assert.deepEqual(result,{ready:false,issue:'service-failed'});
  assert.doesNotMatch(JSON.stringify(localStartupNotice(result.issue)),/private fixture detail/);
});

test('successful local setup stays enabled; cloud-only mode does not show a warning',async()=>{
  const result=await startOptionalLocalRouting({
    enabled:true,start:async()=>{},stop:async()=>assert.fail('healthy engine must stay running'),
  });
  assert.deepEqual(result,{ready:true,issue:null});
  assert.equal(localStartupNotice(result.issue),null);
  assert.equal(localStartupNotice('unknown-untrusted-message'),null);
});

test('protected backend is ready for sign-in while inference still requires authorization',async()=>{
  const server=http.createServer((_request,response)=>{response.writeHead(401);response.end('Sign in');});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const url='http://127.0.0.1:'+server.address().port;
  try{
    await waitForService(url,{allowAuthGate:true,timeoutMs:1000});
    await assert.rejects(waitForService(url,{timeoutMs:150}),/timed out/);
  }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

test('startup retries a warming backend and stops promptly when its process exits',async()=>{
  let requests=0;
  const server=http.createServer((_request,response)=>{response.writeHead(++requests===1?503:200);response.end();});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  try{
    await waitForService('http://127.0.0.1:'+server.address().port,{timeoutMs:1000});
    assert.equal(requests,2);
    await assert.rejects(waitForService('http://127.0.0.1:1',{child:{exitCode:1},timeoutMs:1000}),/exited/);
  }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

test('the package entry starts Electron independently of require.main identity',()=>{
  const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
  const packageInfo=require('./package.json');
  let launched=0;
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,packageInfo.main),'utf8'),{
    require:moduleName=>{assert.equal(moduleName,'./main.cjs');return {launch:()=>launched++};},
    module:{}, // Deliberately not require.main, matching Electron's actual loader.
  });
  assert.equal(launched,1);
});
