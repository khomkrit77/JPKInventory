# JPK Inventory

เว็บแอปภาษาไทยสำหรับทดลองจัดการ IT inventory: Dashboard, Sites, Devices, Users และ Issue Logs พร้อมข้อมูลสมมติ 4 Sites: HQ ลาดพร้าว, AKM เอกมัย, RYT รัชโยธิน และ RST รังสิต มี MikroTik ทุก Site และ Server/NAS เฉพาะ HQ

## เทคโนโลยีและโครงสร้าง

ต่อยอดจากโปรเจกต์เดิมด้วย HTML/CSS + JavaScript ES modules (ไฟล์ preview สร้างเป็น classic script) โดยไม่มี third-party runtime dependency เหมาะกับรุ่นทดลองที่เก็บข้อมูล localStorage ไม่ต้องติดตั้ง Node.js/npm หรือเชื่อมฐานข้อมูล

- `index.html` — จุดเข้าเว็บ
- `src/app.js` — หน้าจอ ฟอร์ม ค้นหา กรอง และ CRUD
- `src/data.js` — ข้อมูลตัวอย่าง, migration, validation, การกรอง Issue และการรักษาประวัติเมื่อมีการลบ
- `src/storage.js` — การอ่านและบันทึก localStorage (จุดแยกสำหรับเปลี่ยนเป็น API ภายหลัง)
- `src/styles.css` — responsive layout สำหรับ desktop/tablet/mobile
- `scripts/serve.py` / `scripts/build.py` — preview และประกอบไฟล์ production
- `tests/` — automated smoke tests และรายการตรวจ UI
- `Dockerfile`, `nginx.conf`, `docker-compose.yml` — production static server

## เปิดดูโดยไม่ต้องใช้ web server

เปิดไฟล์ `index.html` ในโฟลเดอร์ JPKInventory ได้โดยตรง หรือใช้เมนู Open Preview ของ Codex หากมี ไม่ต้องเปิด Python, Docker หรือ localhost ไฟล์นี้รวม CSS และ JavaScript ไว้ในตัวแล้ว

หากแก้ไฟล์ใน `src/` ให้รัน `python3 scripts/make_preview.py` เพื่ออัปเดต `index.html` ก่อนเปิดดูใหม่ การ build จะสร้างไฟล์นี้ให้อัตโนมัติด้วย

การเก็บ localStorage เมื่อเปิดผ่าน `file://` ขึ้นกับเบราว์เซอร์และสิทธิ์ของ preview หากเปิดอ่านได้แต่ไม่อนุญาต storage แอปจะแจ้งข้อผิดพลาด ควรเปิดไฟล์เดิมด้วยเบราว์เซอร์เดิมเพื่อใช้ข้อมูลทดลองต่อ การเปิดผ่าน HTTP ภายหลังเป็นพื้นที่จัดเก็บคนละชุด

## รันในเครื่องผ่าน localhost (ทางเลือก)

ต้องมี Python 3.10+ ไม่มีแพ็กเกจที่ต้องติดตั้ง เปิด Terminal ภายในโฟลเดอร์โปรเจกต์ แล้วรัน:

```sh
cp .env.example .env
python3 scripts/serve.py
```

เปิด **http://localhost:5173** และกด Ctrl+C เพื่อหยุดเซิร์ฟเวอร์ สามารถเปิด `index.html` ผ่าน `file://` โดยตรงได้เช่นกัน เพราะไฟล์ preview รวม JavaScript แบบ classic script แล้ว

เปลี่ยนพอร์ตได้ใน `.env` หรือ `python3 scripts/serve.py --port 5174` การเปลี่ยน origin (scheme/host/port) ทำให้ใช้ localStorage คนละชุด เช่น localhost กับ 127.0.0.1 หรือพอร์ต 5173 กับ 8080

## Build และตรวจสอบ

```sh
python3 scripts/build.py
python3 scripts/serve.py --dist
python3 -m unittest discover -s tests -v
```

Build จะประกอบไฟล์ไว้ใน `dist/` สำหรับ static hosting และไม่รวม `.env` หรือไฟล์เครื่องมือ ไม่มีขั้นตอน transpile/minify ต้องใช้เบราว์เซอร์สมัยใหม่ที่รองรับ dialog, structuredClone, Object.hasOwn และ crypto.randomUUID (เปิดไฟล์โดยตรง, localhost หรือ HTTPS ตามการรองรับของเบราว์เซอร์)

## รันด้วย Docker

ต้องมี Docker Engine/Desktop และ Compose v2:

```sh
cp .env.example .env
# ข้ามคำสั่ง copy หากมี .env ที่ตั้งค่าไว้แล้ว
# Docker build คัดลอก static assets โดยตรง ไม่ต้อง build ด้วย Python ก่อน
docker compose up --build -d
```

เปิด **http://localhost:8080** ตรวจสอบด้วย `docker compose ps` และหยุดด้วย `docker compose down` ใช้ Nginx แบบ non-root ที่พอร์ต 8080 ภายใน container และ health check

`.env.example` มี HOST/PORT สำหรับ Python และ BIND_ADDRESS/APP_PORT สำหรับ Docker ไม่มี secret ในโค้ด ค่าเหล่านี้กำหนดการเปิดพอร์ตที่ host ไม่ได้ถูกฝังใน JavaScript

## การใช้งาน

- Dashboard แสดงยอดตามประเภทและแยก Site คลิกการ์ดสาขาเพื่อกรองอุปกรณ์
- Devices ค้นหา Hostname, IP, MAC, รุ่น, ชื่อประเภทที่กำหนดเอง หรือชื่อ Owner และกรอง Site/ประเภทพร้อมกัน
- ประเภท “อื่นๆ” ต้องระบุชื่อประเภทและ Site แสดงยอดใน Dashboard และหน้า Site เหมือนอุปกรณ์อื่น
- Sites เพิ่มสาขาได้ด้วยรหัสที่ไม่ซ้ำและชื่อสาขา รหัสใช้ 2–12 ตัว A–Z, 0–9, - หรือ _ (เปลี่ยนเป็นตัวพิมพ์ใหญ่ให้อัตโนมัติ) Site ใหม่จะปรากฏใน sidebar และฟอร์มอุปกรณ์/ผู้ใช้
- เพิ่ม/แก้ไข/ลบอุปกรณ์ พร้อมยืนยันการลบและข้อความแจ้งผล
- PC/Notebook มี OS, Start/End MA, Owner และ Folder/Permission ที่เพิ่มลบได้
- PC, Notebook และ Server มี Antivirus active แบบ Yes/No พร้อมแสดงในรายการและหน้ารายละเอียด; Router, NAS และอื่นๆ ไม่แสดงช่องนี้
- ปุ่ม “ดู” ที่ Devices เปิดรายละเอียดอุปกรณ์แบบอ่านอย่างเดียว แล้วกดแก้ไขต่อได้
- Router, Server และ NAS มีข้อมูลพื้นฐาน โดย Server/NAS ล็อกเป็น HQ และ Router ตัวอย่างเป็น MikroTik
- Users มีเบอร์โทรติดต่อและหมายเหตุ แสดงบนการ์ดผู้ใช้และค้นหาได้ เพิ่ม/แก้ไข/ลบได้ Owner เชื่อมด้วย user ID เปลี่ยนชื่อผู้ใช้แล้วอุปกรณ์แสดงชื่อใหม่ การลบผู้ใช้จะล้าง Owner ของอุปกรณ์ที่เชื่อมและมีคำเตือนก่อนยืนยัน
- IP เป็น IPv4 ที่จำเป็นต้องกรอก; MAC เป็นตัวเลือกและรองรับ colon/hyphen; ห้าม Hostname ซ้ำแบบไม่แยกตัวพิมพ์ และ End MA ต้องไม่อยู่ก่อน Start MA
- ป้าย MA คำนวณจากวันที่เครื่อง: หมดอายุ, ใกล้หมดอายุภายใน 30 วัน, อยู่ในประกัน
- บันทึกสำเร็จเฉพาะเมื่อ localStorage เขียนสำเร็จ หากพื้นที่เต็ม/สิทธิ์ถูกปิดจะแสดงข้อผิดพลาด หากข้อมูลที่อ่านเสียหายจะหยุดโหลดโดยไม่เขียนทับข้อมูลเดิม

## Issue Logs

เมนู Issue Logs ใช้ส่วนประกอบและ dialog แบบเดียวกับ Devices/Users รองรับเพิ่ม แก้ไข ดูรายละเอียด และลบพร้อมยืนยัน

- บังคับวันที่เกิดปัญหา, อุปกรณ์/Service, ผู้แจ้ง และ Notes
- วันที่แก้ปัญหาเว้นว่างได้ สถานะเป็น Open; เมื่อกรอกแล้วเป็น Resolved และห้ามอยู่ก่อนวันที่เกิดปัญหา
- เลือกอุปกรณ์จาก Inventory หรือ Service จาก `data.services` (รายการ `{id, name}` ที่มีอยู่ในข้อมูล) โครงสร้างเดิมยังไม่มี Service catalog จึงเริ่มเป็นรายการว่าง และไม่มีหน้าจัดการ Service ในรุ่นนี้ เลือก “อื่นๆ” เพื่อกรอกชื่อ Service/อุปกรณ์เองได้
- ผู้แจ้งเลือกจาก Users หรือเลือก “อื่นๆ” พร้อมระบุชื่อ
- ค้นหาจากชื่ออุปกรณ์/Service, ผู้แจ้ง และ Notes; กรอง Open/Resolved, อุปกรณ์/Service และช่วงวันที่เกิดปัญหาแบบรวมวันเริ่ม/สิ้นสุดได้พร้อมกัน มีปุ่มล้างตัวกรอง
- เมื่อลบอุปกรณ์หรือผู้ใช้ Issue เดิมจะคงวันที่/Notes/สถานะไว้ และเปลี่ยน reference ที่ถูกลบเป็น “อื่นๆ” พร้อมชื่อ ณ เวลาลบ เพื่อเก็บประวัติ

## การรองรับข้อมูลเดิม

ยังใช้ key `jpk-inventory:v1` เดิม แต่ payload เป็น schema `version: 2` เมื่ออ่าน version 1 จะเติม `sites`, `services`, `issues`, `customType`, `antivirusActive`, `phone` และ `notes` ที่ยังไม่มี โดยคง ID, ข้อมูล และฟิลด์เดิมไว้ทั้งหมด ไม่มีการล้าง storage หรือสร้างข้อมูลตัวอย่างทับของเดิม

Migration ทำในหน่วยความจำ และเขียน schema ใหม่เมื่อผู้ใช้บันทึกรายการสำเร็จครั้งถัดไป หากอ่านข้อมูลเสียหาย/เวอร์ชันไม่รองรับ หรือเขียนไม่สำเร็จ จะไม่เขียนทับข้อมูลเดิม ข้อมูลเก่าที่ไม่มี Antivirus จะแสดง “ยังไม่ระบุ” เพื่อไม่ตีความเป็น No และต้องเลือก Yes/No เมื่อบันทึก PC, Notebook หรือ Server ผ่านฟอร์มอีกครั้ง

ยังบังคับ Server/NAS ให้อยู่ HQ เสมอ รวมถึงเมื่อตรวจข้อมูลที่อ่านจาก storage

## ข้อมูลและข้อจำกัดของรุ่นทดลอง

ข้อมูลตัวอย่างสร้างครั้งแรกที่ origin นั้นเท่านั้น หลังแก้ไขหรือรีโหลดจะใช้ข้อมูลที่บันทึกไว้ รวมถึงกรณีลบรายการทั้งหมด หากต้องการเริ่มใหม่ ให้ลบ key `jpk-inventory:v1` ผ่าน DevTools > Application/Storage > Local Storage แล้วรีโหลด (ข้อมูลที่ทดลองแก้จะหาย)

ข้อมูลเก็บที่เบราว์เซอร์ของแต่ละเครื่อง ไม่อยู่ใน Docker volume/server และไม่แชร์ข้ามผู้ใช้/อุปกรณ์ การล้าง browser data ทำให้ข้อมูลหาย ยังไม่มี login, API, database, backup, import/export หรือการควบคุมหลายคนแก้ไขพร้อมกัน แม้จะรับ storage event จากแท็บอื่น แต่ยังเป็นการเขียนข้อมูลทั้งชุดและไม่มี transaction

## แนวทาง deploy บน server / Cloud

1. นำ source ไปที่ server ที่มี Docker และ Compose แล้วสร้าง `.env` จาก `.env.example`
2. ใช้ `docker compose up --build -d` จากโฟลเดอร์โปรเจกต์ ไม่ผูกกับ absolute path ของเครื่องใด
3. ตั้ง reverse proxy (เช่น Nginx/Caddy/load balancer) พร้อมโดเมนและ HTTPS ให้ forward ไป `127.0.0.1:8080` หรือ APP_PORT ที่กำหนด ค่า default เปิดรับเฉพาะ loopback; ถ้าจำเป็นต้องเข้าตรงจากเครือข่าย กำหนด `BIND_ADDRESS=0.0.0.0` และตั้ง firewall ตามการใช้งาน
4. ใช้ `docker compose ps` ตรวจสุขภาพ และ `docker compose logs -f` ดู log; อัปเดต source แล้วรัน `docker compose up --build -d` อีกครั้ง
5. หรือ upload เฉพาะไฟล์ใน `dist/` ไป static hosting ที่รองรับ HTTPS โดยไม่ต้องใช้ Python บน production

การ deploy รุ่นนี้ยังเก็บข้อมูลใน browser ตามเดิม ก่อนใช้ข้อมูลจริงร่วมกัน ควรเปลี่ยน storage layer เป็น API ที่ตรวจสอบข้อมูลฝั่ง server เพิ่ม authentication/authorization, database เช่น PostgreSQL, migrations และ backup โดยบังคับ Server/NAS เฉพาะ HQ ที่ฝั่ง server ด้วย ไม่ใส่รหัสผ่านหรือ secret ใน frontend; เก็บ server secrets ใน environment/secret manager ของผู้ให้บริการเมื่อเพิ่ม backend

## สถานะการตรวจสอบในสภาพแวดล้อมที่สร้าง

ผ่าน automated tests: build/assets และการตรวจ syntax/domain/storage และ runtime template smoke tests ด้วย DOM จำลองของ JavaScript ผ่าน JavaScriptCore บน macOS (บนระบบอื่นชุด JavaScriptCore จะถูก skip) รวมถึง migration v1→v2 ที่ไม่แก้ข้อมูลเดิม, custom type/Site, Antivirus, ข้อมูลผู้ใช้ใหม่, Issue validation/CRUD/filter, การรักษาประวัติเมื่อลบ reference, IP/MAC, HQ constraint, MA, Owner/Folder, persistence, quota failure และข้อมูลเสียหาย ผ่านการตรวจ Compose configuration แต่ยังไม่ได้ build/run Docker image เพราะ Docker daemon ไม่ทำงาน และ preview server ถูก sandbox ปฏิเสธการ bind พอร์ต (`Operation not permitted`) จึงยังไม่ได้ตรวจ UI ในเบราว์เซอร์จริง ใช้ `tests/MANUAL.md` สำหรับตรวจหน้าจอและ CRUD หลังเปิดเซิร์ฟเวอร์ใน Terminal ของเครื่อง
