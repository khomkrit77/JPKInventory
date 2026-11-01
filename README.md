# JPK Inventory

ระบบจัดการผู้ใช้ อุปกรณ์ Sites, Services และ Issue Logs ภาษาไทย ข้อมูลใช้งานจริงเก็บใน SQLite บนเซิร์ฟเวอร์ ผ่าน JSON API ที่ origin เดียวกับเว็บ ไม่มี API URL ภายนอกที่ต้องตั้งค่า

## โครงสร้างและการบันทึก

- `src/app.js`: ฟอร์ม CRUD รอ API ยืนยันก่อนแสดงว่าบันทึกสำเร็จ
- `src/storage.js`: เชื่อม `/api/state`, `/api/import` และส่งออกข้อมูล localStorage เดิม
- `src/data.js`: validation, migration v1 → v2, การรักษาประวัติ Issue เมื่อผู้ใช้/อุปกรณ์ถูกลบ
- `backend/app.py`: WSGI API และ static asset allowlist; production ใช้ Gunicorn 2 workers / 4 threads
- `backend/store.py`: SQLite schema migration 1, foreign keys, WAL, synchronous FULL, atomic transactions และ revision ป้องกัน stale writes
- `backend/manage.py`: integrity check และ online backup ด้วย SQLite backup API
- `index.html`: สร้างจาก `src/` ด้วย `python3 scripts/make_preview.py` ต้องสร้างใหม่ทุกครั้งที่แก้ frontend

SQLite เหมาะกับเว็บ inventory ของทีมบนเซิร์ฟเวอร์เดียวที่มีปริมาณการเขียนไม่สูง ไม่มี DB port เปิดภายนอก หากต้องกระจายหลาย app servers หรือมี concurrent writes จำนวนมากควรเปลี่ยนเป็น PostgreSQL

ข้อมูลแยกตาราง `sites`, `users`, `devices`, `services`, `issues` พร้อม foreign keys ส่วนฟิลด์เดิมและฟิลด์ที่ไม่รู้จักเก็บใน JSON payload เพื่อคงข้อมูลระหว่าง migration การบันทึกทั้งชุดเป็น transaction เดียว API ใช้ revision จากการอ่านครั้งล่าสุด ถ้ามีคนอื่นบันทึกก่อนจะตอบ HTTP 409 โดยไม่เขียนทับ ให้คัดลอกข้อความในฟอร์มแล้วโหลดหน้าใหม่

ฐานข้อมูลใหม่เริ่มจาก 4 Sites และไม่มีผู้ใช้/อุปกรณ์ตัวอย่าง ข้อมูลจากเบราว์เซอร์เดิมต้องนำเข้าเอง ไม่สามารถอ่าน localStorage ของผู้ใช้จากเซิร์ฟเวอร์ได้ การลบผู้ใช้/อุปกรณ์ผ่านเว็บจะรักษาชื่อใน Issue Logs และล้าง Owner ตามเดิม ประวัติก่อนบันทึก 50 ครั้งล่าสุดอยู่ในตาราง `history` ซึ่งไม่ใช้แทน backup ภายนอก

## Deploy บนเซิร์ฟเวอร์

```sh
cd /home/superuser/apps/JPKInventory
# ตรวจและจัดการงานที่ยังไม่ commit ก่อน pull ห้าม reset ทับงาน
 git status --short
 git pull --ff-only origin main
python3 scripts/make_preview.py
mkdir -p "$HOME/jpkinventory-data"
chmod 700 "$HOME/jpkinventory-data"
# สร้างเฉพาะเมื่อยังไม่มี .env; หากมีแล้วให้แก้เฉพาะค่าที่เกี่ยวข้อง
if [ ! -f .env ]; then
  umask 077
  printf 'APP_PORT=8084\nBIND_ADDRESS=0.0.0.0\nDATA_DIR=%s/jpkinventory-data\nAPP_UID=%s\nAPP_GID=%s\n' "$HOME" "$(id -u)" "$(id -g)" > .env
fi
docker compose up -d --build --no-deps inventory
docker compose ps
docker compose logs --tail=50 inventory
curl -f http://127.0.0.1:8084/api/health
```

Host port **8084** map ไป internal **8080**. Bind mount `${DATA_DIR}` → `/data`; ไฟล์จริง `/data/inventory.sqlite3` รวม WAL/SHM อยู่ใน directory ถาวรนอก repo ตัวแปร `APP_UID`/`APP_GID` ต้องตรงกับเจ้าของ directory; runtime เป็น non-root ไม่มีความจำเป็นต้อง chown ด้วย sudo หากใช้ directory ของ SSH user เอง ค่าเริ่มต้น image UID/GID 10001

Container filesystem เป็น read-only ยกเว้น `/data` และ `/tmp` กำหนด log rotation และ health check ที่ทดสอบอ่านฐานข้อมูลจริง การ recreate/rebuild `inventory` ไม่แตะข้อมูลใน bind mount อย่าใช้ `down -v`, prune หรือคำสั่งล้าง volume

ไม่มีระบบ login/role ในรุ่นนี้ ผู้ที่เข้าถึงเว็บได้สามารถอ่านและแก้ inventory ได้ เช่นเดียวกับระบบเดิม หากเปิด internet ควรจำกัด source IP/VPN หรือวาง HTTPS reverse proxy พร้อม authentication ก่อนนำข้อมูลอ่อนไหวมาใช้ HTTP port 8084 ใช้งานได้โดยไม่ต้องเปลี่ยน browser flags

ตรวจ firewall ก่อนเปลี่ยน: host firewall, router/NAT และ cloud security group (ถ้ามี) ต้องยอมรับ TCP 8084 จากเครือข่ายผู้ใช้ อย่าเปิดกว้างหรือแก้กฎโดยไม่ตรวจสภาพแวดล้อมจริง

## นำข้อมูล localStorage เดิมเข้า database

1. เปิดเว็บด้วย browser/profile และ **origin เดิม** (scheme, host และ port เดียวกัน) ที่เคยมีข้อมูล
2. หน้าใหม่กด **นำเข้า / ส่งออกข้อมูล → ส่งออก localStorage เดิม** เก็บ JSON ไว้ โดยระบบไม่ลบ key `jpk-inventory:v1`
3. เลือก JSON แล้วกด **นำเข้าข้อมูล** ระบบดาวน์โหลดสำเนาข้อมูลส่วนกลางก่อนนำเข้า และรวมข้อมูลตาม ID ใน transaction เดียว
4. ถ้า ID ซ้ำแต่เนื้อหาต่าง ระบบหยุดทั้งชุดพร้อมบอก collection/ID ข้อมูลบนเซิร์ฟเวอร์ยังอยู่ ให้ตรวจ JSON และแก้ conflict โดยรักษาความสัมพันธ์ ID ก่อนนำเข้าใหม่ ไม่ควรเปลี่ยน ID ผู้ใช้/อุปกรณ์โดยไม่ปรับ references
5. โหลดหน้าใหม่หรือเปิดอีก browser ตรวจว่ารายการปรากฏจากเซิร์ฟเวอร์

หากยังเปิดหน้าเดิมอยู่ สามารถส่งออกจาก DevTools Console:

```js
const raw = localStorage.getItem('jpk-inventory:v1');
if (!raw) throw new Error('No legacy data at this origin');
const a = document.createElement('a');
a.href = URL.createObjectURL(new Blob([raw], {type:'application/json'}));
a.download = 'jpkinventory-localstorage.json';
a.click();
```

การเปิด `index.html` ผ่าน `file://` ยังคงเป็น offline demo ที่ใช้ localStorage ของไฟล์นั้นเท่านั้น การเปิดผ่าน HTTP จะต้องมี API; ไม่มีการ fallback เงียบไปเก็บใน browser เมื่อ API ล้มเหลว

## Backup / Restore

สำรองขณะระบบทำงานได้ด้วย SQLite backup API ห้าม copy เฉพาะไฟล์ `.sqlite3` ขณะ WAL ยังมีการเขียน:

```sh
cd /home/superuser/apps/JPKInventory
stamp=$(date +%Y%m%d-%H%M%S)
docker compose exec -T inventory python -m backend.manage backup "/data/backups/inventory-$stamp.sqlite3"
docker compose exec -T inventory python -m backend.manage check
```

ไฟล์ backup อยู่ที่ `${DATA_DIR}/backups/` นอก container ควรคัดลอกไปอีกเครื่อง/ระบบสำรองด้วยสิทธิ์จำกัดและกำหนดรอบสำรองตามข้อมูลที่ยอมเสียได้ ซอร์สและการตั้งค่าก่อน deploy แยกเก็บนอก repo ด้วย; ข้อมูล browser เดิมต้องสำรอง JSON ตามขั้นตอนข้างต้น

Restore ให้หยุดเฉพาะ service นี้และสำรองสถานะปัจจุบันก่อนเสมอ (เปลี่ยนชื่อไฟล์ backup ให้ถูกต้อง):

```sh
docker compose stop inventory
docker compose run --rm --no-deps inventory python -m backend.manage restore /data/backups/inventory-YYYYMMDD-HHMMSS.sqlite3
docker compose up -d --no-deps inventory
docker compose exec -T inventory python -m backend.manage check
```

คำสั่ง restore ตรวจ integrity/schema/relationships ก่อนใช้ SQLite backup API คืนข้อมูล และสร้าง `before-restore-*.sqlite3` ก่อนเสมอ อย่าสั่ง restore ขณะที่ app container ยังทำงาน

## ทดสอบ

```sh
python3 scripts/make_preview.py
python3 -m unittest discover -s tests -v
# local full-stack development (database ignored by Git)
DATABASE_PATH=/tmp/jpkinventory-dev.sqlite3 python3 -m backend.dev
```

`tests/test_backend.py` ทดสอบ API, CRUD ทุก collection, stale revision, invalid references, import, migration, backup/reopen และ static allowlist; JavaScriptCore tests ใช้ macOS ทดสอบ domain/storage/template ส่วน UI จริงให้ทดสอบผ่าน browser ที่พอร์ต 8084: เพิ่ม แก้ ลบ Users/Devices/Issues และเพิ่ม Site แล้ว reload ตรวจข้อมูล จากนั้น `docker compose up -d --force-recreate --no-deps inventory` และตรวจว่าข้อมูลยังอยู่

ห้าม commit `.env`, database, WAL/SHM, backup หรือข้อมูลจริง; `.gitignore` และ `.dockerignore` กันไฟล์เหล่านี้ไว้แล้ว
