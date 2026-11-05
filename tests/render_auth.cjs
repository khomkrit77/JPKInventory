const fs=require('fs'),vm=require('vm');
// Run from the project root with Node.js: node tests/render_auth.cjs
const strip=s=>s.replace(/^import .*?;\s*/gm,'').replace(/^export /gm,'');
let code=`const location={protocol:'file:'};const MutationObserver=class{observe(){}};function assert(ok,msg){if(!ok)throw Error(msg)};const localStorage={getItem(){return null},setItem(){}};`;
code+=fs.readFileSync('tests/render.js','utf8');
for(const f of ['data','storage','app'])code+=strip(fs.readFileSync('src/'+f+'.js','utf8')).replace(/\nstart\(\);\s*$/,'')+'\n';
code+='data=load();'+fs.readFileSync('tests/render_checks.js','utf8');
code+=`
location.protocol='http:';failure='';page='dashboard';
currentAccount={id:'a1',username:'admin',role:'admin',permission:'read/write',mustChange:false};shell();
assert($('#app').innerHTML.includes('User Management'),'Admin sees management tab');
currentAccount={id:'r1',username:'reader',role:'user',permission:'read-only'};shell();
assert(!$('#app').innerHTML.includes('User Management'),'Reader cannot see management tab');assert(!canWrite(),'Reader cannot write');
$('#auth-form').elements={password:{},newPassword:{},confirmPassword:{}};
authScreen();assert($('#app').innerHTML.includes('Sign in'),'Login renders');
authScreen(true);assert($('#app').innerHTML.includes('Confirm new password'),'Password change renders');
currentAccount={id:'a1',username:'admin',role:'admin'};
const fetch=async()=>({ok:true,json:async()=>({users:[{id:'a1',username:'admin',role:'admin',permission:'read/write',active:true,mustChange:false},{id:'r1',username:'reader<script>',role:'user',permission:'read-only',active:false,mustChange:true}]})});
accountsPage().then(()=>{assert($('#account-list').innerHTML.includes('reader&lt;script&gt;'),'Account names escaped');assert($('#account-list').innerHTML.includes('Disabled'),'Account status renders');console.log('Inventory and authentication render checks passed')});
`;
vm.runInNewContext(code,{console,setTimeout,clearTimeout,crypto:require('crypto').webcrypto},{filename:'render-smoke.js'});
