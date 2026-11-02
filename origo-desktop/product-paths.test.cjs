const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {productPaths}=require('./product-paths.cjs');

test('development keeps its existing runtime and profile locations',()=>{
 const root=path.join(os.tmpdir(),'indra-path-contract');
 const p=productPaths({root,env:{},localAppData:os.tmpdir()});
 assert.equal(p.python,path.join(root,'.indra-python','Scripts','python.exe'));
 assert.equal(p.home,path.join(root,'data','indra-product-home'));
});
test('a packaged app uses bundled Python and keeps state outside the installation',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'indra-bundle-path-'));
 fs.mkdirSync(path.join(root,'runtime','python'),{recursive:true});
 fs.writeFileSync(path.join(root,'runtime','python','python.exe'),'fixture');
 const p=productPaths({root,env:{},packaged:true,localAppData:path.join(os.tmpdir(),'judge-user')});
 assert.equal(p.python,path.join(root,'runtime','python','python.exe'));
 assert.equal(p.home,path.join(os.tmpdir(),'judge-user','OrigoLabs','Indra','profile'));
 assert.ok(!p.home.startsWith(root));
});
test('explicit isolated acceptance profile and runtime overrides are respected',()=>{
 const p=productPaths({root:os.tmpdir(),env:{ORIGO_HOME:'./qa-profile',ORIGO_LOG_DIR:'./qa-logs',ORIGO_PYTHON:'./portable-python.exe'},packaged:true,localAppData:os.tmpdir()});
 assert.equal(p.home,path.resolve('qa-profile'));
 assert.equal(p.logs,path.resolve('qa-logs'));
 assert.equal(p.python,path.resolve('portable-python.exe'));
});
