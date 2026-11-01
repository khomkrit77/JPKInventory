export const sites = [{id:'HQ',name:'ลาดพร้าว',detail:'สำนักงานใหญ่ · ศูนย์กลางระบบไอที'},{id:'AKM',name:'เอกมัย',detail:'สำนักงานสาขาเอกมัย'},{id:'RYT',name:'รัชโยธิน',detail:'สำนักงานสาขารัชโยธิน'},{id:'RST',name:'รังสิต',detail:'สำนักงานสาขารังสิต'}];
export const types = {server:'Server',pc:'PC',notebook:'Notebook',nas:'NAS',router:'Router',other:'อื่นๆ'};
export const permissions = ['Read','Write','Read/Write'];
export function seed() {
 const users = [{id:'u1',name:'กานต์ ธนากุล',department:'เทคโนโลยีสารสนเทศ',site:'HQ',contact:'kant@example.test'},{id:'u2',name:'พิมพ์ชนก วงศ์ดี',department:'บัญชี',site:'HQ',contact:'pim@example.test'},{id:'u3',name:'ณัฐพล สุขใจ',department:'ฝ่ายขาย',site:'AKM',contact:'nat@example.test'},{id:'u4',name:'อรทัย ใจดี',department:'ปฏิบัติการ',site:'RYT',contact:'orn@example.test'},{id:'u5',name:'ธนวัฒน์ พูนผล',department:'บุคคล',site:'RST',contact:'tan@example.test'}];
 const base = {mac:'',os:'',startMA:'',endMA:'',ownerId:'',folders:[],model:'',notes:''};
 const devices = sites.map((s,i)=>({...base,id:`r${i}`,hostname:`${s.id}-RTR-01`,type:'router',site:s.id,ip:`192.168.${i+10}.1`,mac:`02:00:00:00:0${i}:01`,model:i===0?'MikroTik RB5009':'MikroTik hEX S',notes:'Gateway ประจำสาขา'}));
 devices.push({...base,id:'s1',hostname:'HQ-SRV-01',type:'server',site:'HQ',ip:'192.168.10.10',model:'Dell PowerEdge R350',notes:'ระบบงานภายใน'},{...base,id:'n1',hostname:'HQ-NAS-01',type:'nas',site:'HQ',ip:'192.168.10.20',model:'Synology DS923+',notes:'พื้นที่จัดเก็บไฟล์ส่วนกลาง'});
 users.forEach((u,i)=>devices.push({...base,id:`d${i}`,hostname:`${u.site}-${i%2?'PC':'NB'}-01`,type:i%2?'pc':'notebook',site:u.site,ip:`192.168.${sites.findIndex(s=>s.id===u.site)+10}.${101+i}`,mac:`02:AA:BB:CC:DD:0${i}`,os:'Windows 11 Pro',startMA:'2026-01-01',endMA:i===1?'2026-10-01':'2027-12-31',ownerId:u.id,model:i%2?'Dell OptiPlex 7010':'Lenovo ThinkPad E14',folders:[{name:'Shared',permission:'Read'},{name:u.department,permission:'Read/Write'}]}));
 devices.forEach(d=>d.antivirusActive=['pc','notebook','server'].includes(d.type)?'yes':null);
 return migrate({version:1,users,devices});
}
export function validateDevice(d, users, availableSites=sites) {
 const errors={};
 if(!d.hostname?.trim()) errors.hostname='กรุณาระบุชื่อ / Hostname';
 if(!Object.hasOwn(types,d.type)) errors.type='ประเภทอุปกรณ์ไม่ถูกต้อง';
 if(!availableSites.some(s=>s.id===d.site)) errors.site='กรุณาเลือก Site';
 if(['server','nas'].includes(d.type)&&d.site!=='HQ') errors.site='Server และ NAS ต้องอยู่ที่ HQ เท่านั้น';
 if(!/^(\d{1,3}\.){3}\d{1,3}$/.test(d.ip)||d.ip.split('.').some(n=>Number(n)>255)) errors.ip='กรุณาระบุ IPv4 เช่น 192.168.10.100 (แต่ละส่วน 0–255)';
 if(d.mac&&!/^([0-9a-f]{2}:){5}[0-9a-f]{2}$/i.test(d.mac)&&!/^([0-9a-f]{2}-){5}[0-9a-f]{2}$/i.test(d.mac)) errors.mac='ใช้รูปแบบ AA:BB:CC:DD:EE:FF หรือ AA-BB-CC-DD-EE-FF';
 if(d.ownerId&&!users.some(u=>u.id===d.ownerId)) errors.ownerId='ไม่พบผู้ใช้งานที่เลือก';
 if(d.type==='other'&&!d.customType?.trim()) errors.customType='กรุณาระบุชื่อประเภทอุปกรณ์';
 if(['pc','notebook','server'].includes(d.type)&&!['yes','no'].includes(d.antivirusActive)) errors.antivirusActive='กรุณาเลือก Antivirus active เป็น Yes หรือ No';
 for(const key of ['startMA','endMA']) if(d[key]&&!isISODate(d[key])) errors[key]='กรุณาระบุวันที่ที่ถูกต้อง';
 if(d.startMA&&d.endMA&&d.endMA<d.startMA) errors.endMA='End MA ต้องไม่อยู่ก่อน Start MA';
 if(d.folders?.some(f=>!f.name.trim()||!permissions.includes(f.permission))) errors.folders='กรุณาระบุชื่อ Folder และ Permission ให้ครบ';
 return errors;
}

// Keep the original localStorage key; migration only adds missing fields in memory.
export function migrate(raw) {
 if(!raw||![1,2].includes(raw.version)||!Array.isArray(raw.users)||!Array.isArray(raw.devices)) throw Error('โครงสร้างข้อมูลไม่ถูกต้อง');
 return {...raw,version:2,
  sites:raw.sites===undefined?sites.map(s=>({...s})):raw.sites,
  services:raw.services===undefined?[]:raw.services,
  issues:raw.issues===undefined?[]:raw.issues,
  users:raw.users.map(u=>({phone:'',notes:'',...u})),
  devices:raw.devices.map(d=>({customType:'',antivirusActive:null,...d}))};
}
export function isISODate(value) {
 if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value)||value.startsWith('0000')) return false;
 const date=new Date(value+'T00:00:00Z');
 return !Number.isNaN(date.getTime())&&date.toISOString().slice(0,10)===value;
}
export function validateSite(site, availableSites) {
 const errors={};
 if(!/^[A-Z0-9][A-Z0-9_-]{1,11}$/.test(site.id)) errors.id='ใช้รหัส 2–12 ตัว: A–Z, 0–9, - หรือ _';
 if(availableSites.some(s=>s.id.toUpperCase()===site.id.toUpperCase())) errors.id='รหัส Site นี้มีอยู่แล้ว';
 if(!site.name?.trim()) errors.name='กรุณาระบุชื่อสาขา';
 return errors;
}
export function targetName(issue, data) {
 return (issue.targetKind==='device'?data.devices.find(d=>d.id===issue.targetId)?.hostname:issue.targetKind==='service'?data.services.find(s=>s.id===issue.targetId)?.name:null)||issue.targetName;
}
export function reporterName(issue, data) {
 return (issue.reporterKind==='user'?data.users.find(u=>u.id===issue.reporterId)?.name:null)||issue.reporterName;
}
export function validateIssue(issue, data) {
 const errors={};
 if(!isISODate(issue.occurredOn)) errors.occurredOn='กรุณาระบุวันที่เกิดปัญหาที่ถูกต้อง';
 if(issue.resolvedOn&&!isISODate(issue.resolvedOn)) errors.resolvedOn='กรุณาระบุวันที่แก้ปัญหาที่ถูกต้อง';
 if(isISODate(issue.occurredOn)&&isISODate(issue.resolvedOn)&&issue.resolvedOn<issue.occurredOn) errors.resolvedOn='วันที่แก้ปัญหาต้องไม่อยู่ก่อนวันที่เกิดปัญหา';
 if(!['device','service','other'].includes(issue.targetKind)) errors.target='กรุณาเลือกอุปกรณ์หรือ Service';
 else if(issue.targetKind==='other') {if(!issue.targetName?.trim()) errors.targetName='กรุณาระบุชื่ออุปกรณ์หรือ Service';}
 else if(!(issue.targetKind==='device'?data.devices:data.services).some(x=>x.id===issue.targetId)) errors.target='ไม่พบอุปกรณ์หรือ Service ที่เลือก';
 if(!['user','other'].includes(issue.reporterKind)) errors.reporter='กรุณาเลือกผู้แจ้ง';
 else if(issue.reporterKind==='other') {if(!issue.reporterName?.trim()) errors.reporterName='กรุณาระบุชื่อผู้แจ้ง';}
 else if(!data.users.some(u=>u.id===issue.reporterId)) errors.reporter='ไม่พบผู้แจ้งที่เลือก';
 if(!issue.notes?.trim()) errors.notes='กรุณาระบุรายละเอียดปัญหา';
 return errors;
}
export function filterIssues(data, filters) {
 const q=(filters.query||'').toLocaleLowerCase();
 return data.issues.filter(issue=>{
  const status=issue.resolvedOn?'resolved':'open';
  const target=issue.targetKind==='other'?`other:${issue.targetName}`:`${issue.targetKind}:${issue.targetId}`;
  return (!filters.status||filters.status===status)&&(!filters.from||issue.occurredOn>=filters.from)&&(!filters.to||issue.occurredOn<=filters.to)&&(!filters.target||filters.target===target||(filters.target==='other'&&issue.targetKind==='other'))&&[targetName(issue,data),reporterName(issue,data),issue.notes].some(v=>v.toLocaleLowerCase().includes(q));
 }).sort((a,b)=>b.occurredOn.localeCompare(a.occurredOn));
}
// Preserve issue history when inventory records are removed.
export function removeEntity(data, kind, id) {
 if(kind==='issue') return {...data,issues:data.issues.filter(x=>x.id!==id)};
 if(kind==='user') return {...data,users:data.users.filter(u=>u.id!==id),devices:data.devices.map(d=>d.ownerId===id?{...d,ownerId:''}:d),issues:data.issues.map(i=>i.reporterKind==='user'&&i.reporterId===id?{...i,reporterKind:'other',reporterId:'',reporterName:reporterName(i,data)}:i)};
 return {...data,devices:data.devices.filter(d=>d.id!==id),issues:data.issues.map(i=>i.targetKind==='device'&&i.targetId===id?{...i,targetKind:'other',targetId:'',targetName:targetName(i,data)}:i)};
}
