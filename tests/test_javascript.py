"""Run domain/storage tests with macOS JavaScriptCore when Node is absent."""
import ctypes
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(sys.platform == 'darwin', 'JavaScriptCore test runner requires macOS')
class JavaScriptTests(unittest.TestCase):
    def test_javascript_domain_storage_and_syntax(self):
        lib = ctypes.CDLL('/System/Library/Frameworks/JavaScriptCore.framework/JavaScriptCore')
        ptr = ctypes.c_void_p
        lib.JSGlobalContextCreate.argtypes = [ptr]
        lib.JSGlobalContextCreate.restype = ptr
        lib.JSStringCreateWithUTF8CString.argtypes = [ctypes.c_char_p]
        lib.JSStringCreateWithUTF8CString.restype = ptr
        lib.JSEvaluateScript.argtypes = [ptr, ptr, ptr, ptr, ctypes.c_int, ctypes.POINTER(ptr)]
        lib.JSEvaluateScript.restype = ptr
        lib.JSValueToStringCopy.argtypes = [ptr, ptr, ctypes.POINTER(ptr)]
        lib.JSValueToStringCopy.restype = ptr
        lib.JSStringGetMaximumUTF8CStringSize.argtypes = [ptr]
        lib.JSStringGetMaximumUTF8CStringSize.restype = ctypes.c_size_t
        lib.JSStringGetUTF8CString.argtypes = [ptr, ctypes.c_char_p, ctypes.c_size_t]
        lib.JSStringRelease.argtypes = [ptr]
        lib.JSGlobalContextRelease.argtypes = [ptr]
        ctx = lib.JSGlobalContextCreate(None)
        def evaluate(code):
            source = lib.JSStringCreateWithUTF8CString(code.encode())
            error = ptr()
            lib.JSEvaluateScript(ctx, source, None, None, 1, ctypes.byref(error))
            lib.JSStringRelease(source)
            if error.value:
                message = lib.JSValueToStringCopy(ctx, error, None)
                size = lib.JSStringGetMaximumUTF8CStringSize(message)
                buffer = ctypes.create_string_buffer(size)
                lib.JSStringGetUTF8CString(message, buffer, size)
                lib.JSStringRelease(message)
                self.fail(buffer.value.decode())
        try:
            import json
            preview = (ROOT / 'index.html').read_text()
            scripts = re.findall(r'<script>([\s\S]*?)</script>', preview)
            self.assertEqual(len(scripts), 1)
            evaluate('new Function(' + json.dumps(scripts[0]) + ');')
            for file in ['data.js', 'storage.js', 'app.js']:
                code = (ROOT / 'src' / file).read_text()
                code = re.sub(r'^import .*?;\s*', '', code, flags=re.M)
                code = re.sub(r'\bexport ', '', code)
                evaluate('new Function(' + json.dumps(code) + ');')
                if file != 'app.js':
                    evaluate(code)
            evaluate('''
function assert(ok, msg) { if (!ok) throw Error(msg); }
let raw = null, blocked = false;
const localStorage = {
 getItem() { return raw; },
 setItem(k,v) { if (blocked) throw Error('quota'); raw=v; }
};
const initial = load();
assert(initial.devices.length===11 && initial.users.length===5,'Seed counts');
assert(sites.every(s=>initial.devices.some(d=>d.site===s.id&&d.type==='router')),'Router at each site');
assert(initial.devices.filter(d=>['server','nas'].includes(d.type)).every(d=>d.site==='HQ'),'HQ restriction');
assert(initial.devices.every(d=>Object.keys(validateDevice(d,initial.users)).length===0),'Valid seed devices');
const pc=initial.devices.find(d=>d.type==='pc');
for (const ip of ['999.1.1.1','1.2.3','a.1.2.3','1.2.3.4.5','-1.2.3.4','']) assert(validateDevice({...pc,ip},initial.users).ip,'Reject IP '+ip);
for (const ip of ['0.0.0.0','255.255.255.255','192.168.1.10']) assert(!validateDevice({...pc,ip},initial.users).ip,'Accept IP '+ip);
for (const mac of ['AA:BB:CC:DD:EE:FF','aa-bb-cc-dd-ee-ff','']) assert(!validateDevice({...pc,mac},initial.users).mac,'Accept MAC');
assert(validateDevice({...pc,mac:'XX:BB:CC:DD:EE:FF'},initial.users).mac,'Reject MAC');
assert(validateDevice({...pc,type:'server',site:'AKM'},initial.users).site,'Reject remote server');
assert(validateDevice({...pc,type:'nas',site:'RST'},initial.users).site,'Reject remote NAS');
assert(validateDevice({...pc,startMA:'2027-01-01',endMA:'2026-01-01'},initial.users).endMA,'MA order');
assert(validateDevice({...pc,ownerId:'missing'},initial.users).ownerId,'Owner integrity');
assert(validateDevice({...pc,folders:[{name:'',permission:'Read'}]},initial.users).folders,'Folder name required');
assert(validateDevice({...pc,folders:[{name:'test',permission:'Admin'}]},initial.users).folders,'Folder permission enum');
const changed={...initial,devices:initial.devices.slice(1)};
save(changed); assert(load().devices.length===10,'Persistence');
const before=raw; blocked=true;
let failed=false;try {save(initial);} catch {failed=true;}
assert(failed&&raw===before,'Failed write leaves existing storage intact');blocked=false;
save({...initial,devices:[]});assert(load().devices.length===0,'Empty records do not reseed');
raw='{invalid';failed=false;try{load();}catch{failed=true;}assert(failed&&raw==='{invalid','Corrupt data not overwritten');
save({...initial,devices:[{...pc,ownerId:'missing'}]});failed=false;try{load();}catch{failed=true;}assert(failed,'Stored owner validation');
save({...initial,devices:[{...pc,type:'nas',site:'AKM'}]});failed=false;try{load();}catch{failed=true;}assert(failed,'Stored location validation');
''')
            evaluate((ROOT / 'tests/features.js').read_text())
            evaluate('raw=JSON.stringify(initial);')
            app_code=re.sub(r'\nshell\(\);\s*$', '', code)
            evaluate('(function(){' + (ROOT / 'tests/render.js').read_text() + app_code + (ROOT / 'tests/render_checks.js').read_text() + '})();')
        finally:
            lib.JSGlobalContextRelease(ctx)

if __name__ == '__main__':
    unittest.main()
