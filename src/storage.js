import {seed,migrate,types,permissions,validateIssue} from './data.js';
const KEY='jpk-inventory:v1';
export function load() {
 const raw=localStorage.getItem(KEY);
 if(!raw) {const data=seed(); save(data); return data;}
 const data=migrate(JSON.parse(raw));
 if(!Array.isArray(data.sites)||!Array.isArray(data.services)||!Array.isArray(data.issues)) throw Error('โครงสร้างข้อมูลไม่ถูกต้อง');
 const siteIds=new Set();
 for(const s of data.sites) {
  if(!s||typeof s.id!=='string'||!/^[A-Z0-9][A-Z0-9_-]{1,11}$/.test(s.id)||siteIds.has(s.id)||typeof s.name!=='string'||!s.name.trim()||(s.detail!==undefined&&typeof s.detail!=='string')) throw Error('ข้อมูล Site ไม่ถูกต้อง');
  siteIds.add(s.id);
 }
 if(!siteIds.has('HQ')) throw Error('ไม่พบ HQ');
 const ids=new Set();
 for(const item of [...data.users,...data.devices,...data.services,...data.issues]) {if(!item||typeof item.id!=='string'||!item.id||ids.has(item.id)) throw Error('ข้อมูลรายการไม่ถูกต้อง'); ids.add(item.id);}
 for(const u of data.users) if(!['name','department','contact','phone','notes'].every(k=>typeof u[k]==='string')||!siteIds.has(u.site)) throw Error('ข้อมูลผู้ใช้ไม่ถูกต้อง');
 for(const s of data.services) if(typeof s.name!=='string'||!s.name.trim()) throw Error('ข้อมูล Service ไม่ถูกต้อง');
 for(const d of data.devices) if(!Object.hasOwn(types,d.type)||!siteIds.has(d.site)||!['hostname','ip','mac','os','startMA','endMA','ownerId','model','notes','customType'].every(k=>typeof d[k]==='string')||(d.type==='other'&&!d.customType.trim())||![null,'yes','no'].includes(d.antivirusActive)||!Array.isArray(d.folders)||d.folders.some(f=>!f||typeof f.name!=='string'||!permissions.includes(f.permission))||(['server','nas'].includes(d.type)&&d.site!=='HQ')||(d.ownerId&&!data.users.some(u=>u.id===d.ownerId))) throw Error('ข้อมูลอุปกรณ์ไม่ถูกต้อง');
 for(const i of data.issues) if(!['occurredOn','resolvedOn','targetKind','targetId','targetName','reporterKind','reporterId','reporterName','notes'].every(k=>typeof i[k]==='string')||Object.keys(validateIssue(i,data)).length) throw Error('ข้อมูล Issue Log ไม่ถูกต้อง');
 return data;
}
export function save(data) {localStorage.setItem(KEY,JSON.stringify(data));}
