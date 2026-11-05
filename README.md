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

ระบบต้องลงชื่อเข้าใช้ด้วยบัญชี local และตรวจสิทธิ์ที่ API ดูวิธีตั้งค่าในหัวข้อ Local login accounts ด้านล่าง

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

### Local login accounts

The server now requires login for inventory API access. On the first start after
this update, it adds a local `admin` account with password `JpkAdmin2026` (or the
`ADMIN_PASSWORD` environment value). The first login requires a new password.
Existing inventory is preserved, and subsequent starts never reset credentials.
Set `ADMIN_PASSWORD` before starting Docker Compose to choose the initial password.
Set `COOKIE_SECURE=1` when serving through an HTTPS reverse proxy.

Admins use **User Management** to create/delete login accounts, assign the `admin`
or `user` role, set permissions, disable accounts, reset passwords, and require a
password change. This tab is separate from **Users**, which lists inventory owners.
Admins have full access. Ordinary users with `read-only` can view inventory;
`read/write` users can view, create and update. Only admins can delete records.

Passwords must have 8–256 characters including a letter and a number. Generated
temporary passwords are shown once after saving and always require a change.
Use the **Password** button to change your own password. Password changes,
account edits, disabling, and deletion revoke the affected user's sessions.
Sessions expire after eight hours; signing out revokes the current session.
Login attempts are limited to ten failures per source address per fifteen minutes.
Passwords are salted and hashed with scrypt; session tokens are stored as hashes.
Inventory JSON import/export excludes login accounts. SQLite backups include them.
The standalone `file://` preview remains an offline demo; login and account
management require the Python server.

Run checks with `python3 -m unittest discover -s tests -v`.

## Deployment file structure and setup guidelines

### Required files

Use the same application layout on public cloud VMs, private/local cloud VMs,
and custom Linux servers:

```text
JPKInventory/
├── Dockerfile                 # Python/Gunicorn runtime image
├── docker-compose.yml         # Service, persistent storage, port and health check
├── requirements.txt           # Python runtime dependencies
├── .env.example               # Configuration template (tracked)
├── .env                       # Host-specific configuration (not committed)
├── index.html                 # Generated application entrypoint
├── backend/
│   ├── __init__.py
│   ├── app.py                 # WSGI API and allowlisted static assets
│   ├── auth.py                # Login accounts, password rules and sessions
│   ├── store.py               # SQLite persistence and migrations
│   ├── manage.py              # Database checks, backup and restore
│   └── dev.py                 # Local development server only
├── src/
│   ├── app.js
│   ├── storage.js
│   ├── data.js
│   └── styles.css
├── scripts/
│   ├── make_preview.py        # Regenerate index.html after frontend changes
│   └── build.py               # Also generate optional dist/ static output
└── tests/                     # API, authentication and render checks

/path/outside/repository/jpkinventory-data/
├── inventory.sqlite3          # Created automatically on first startup
├── inventory.sqlite3-wal      # SQLite-managed runtime file, when present
├── inventory.sqlite3-shm      # SQLite-managed runtime file, when present
└── backups/                   # Created when database backups are requested
```

For container deployment, retain `Dockerfile`, `docker-compose.yml`,
`requirements.txt`, `index.html`, `backend/`, and `src/`. Keep `scripts/` when
building from source and `tests/` when validating a release. `dist/` is optional
and is not used by the container. Static hosting alone cannot provide login,
account management or persistent inventory: the Python API must run as well.
The included `nginx.conf` is a legacy static-site configuration, not a complete
reverse proxy configuration for the authenticated app.

### Common setup: Docker Compose

Prerequisites: a Linux host with Docker Engine and the Docker Compose plugin,
Git, Python 3 for generating frontend assets, and a persistent local disk.
The image installs its own Python dependencies. Run one application service
with one shared SQLite directory; do not scale replicas across hosts or place
the database on a shared network filesystem.

```sh
git clone https://github.com/khomkrit77/JPKInventory.git
cd JPKInventory
python3 scripts/make_preview.py

# Fresh installation only; preserve an existing .env when updating.
cp .env.example .env
chmod 600 .env
mkdir -p "$HOME/jpkinventory-data"
chmod 700 "$HOME/jpkinventory-data"
id -u
id -g
```

Before starting, edit `.env` with values appropriate to the host:

| Variable | Setup guideline |
| --- | --- |
| `DATA_DIR` | Absolute path to the persistent directory created above; do not leave the example `/home/superuser/...` path on another host. |
| `APP_UID`, `APP_GID` | Numeric owner IDs of `DATA_DIR`; use the output of `id -u` and `id -g` when the directory belongs to the current user. |
| `APP_PORT` | Host listening port, default `8084`; the container listens on `8080`. |
| `BIND_ADDRESS` | `127.0.0.1` for a reverse proxy on the same host, or the host's private interface address for direct LAN access. |
| `ADMIN_PASSWORD` | Initial local admin password: at least 8 characters with letters and numbers. Used only when the initial account is created. |
| `COOKIE_SECURE` | `1` when users access the app over HTTPS; `0` for direct local HTTP. |

```sh
docker compose up -d --build --wait
docker compose ps
docker compose logs --tail=50 inventory
curl --fail http://127.0.0.1:8084/api/health
```

Use the configured interface and port for the health request if binding to a
private address instead of loopback. Open the application URL, sign in as
`admin` with the initial password, and complete the required password change.
Then create individual accounts through **User Management**. To validate API
protection, an unauthenticated request to `/api/state` must return HTTP `401`.

### Public cloud

Provision a VM with persistent block storage and follow the common setup above.
Keep `DATA_DIR` on a disk that survives container replacement and configure
backups outside the VM. Configure a DNS name and an HTTPS reverse proxy or load
balancer that forwards **all paths**, including `/api/*`, to the application.
Keep the UI and API on the same public origin.

For a reverse proxy running directly on the same host, use
`BIND_ADDRESS=127.0.0.1` and upstream `http://127.0.0.1:8084`. For an external
load balancer, bind to a private interface and permit backend traffic only from
that load balancer. A proxy running in another container needs a reachable
container-network upstream rather than its own loopback address. Set
`COOKIE_SECURE=1` for HTTPS access. Allow HTTPS through the cloud security group
and host firewall, restrict management access, and keep the backend port out of
public ingress. A platform offering only static hosting or ephemeral storage
needs a different backend/storage architecture to run this application.

### Local cloud / private cloud

Create a Linux VM with persistent local storage on your private infrastructure
and follow the same Docker Compose setup. Bind to the VM's private address for
LAN access, or loopback when a reverse proxy runs on that VM. Permit the chosen
port only from intended LAN/VPN networks in both host and virtual-network
firewalls. Configure private DNS or access `http://<private-ip>:8084` for local
HTTP deployments. Use an HTTPS reverse proxy and `COOKIE_SECURE=1` when serving
HTTPS. VM snapshots supplement the SQLite-aware backups described above.

### Custom server / installation without Docker

A physical server or a custom Linux VM can use Docker Compose exactly as above.
For a native installation, use Python 3.13 (matching the Docker image), a virtual
environment, and the same `backend/`, `src/` and generated `index.html` files:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/make_preview.py
mkdir -p "$HOME/jpkinventory-data"
chmod 700 "$HOME/jpkinventory-data"
export DATABASE_PATH="$HOME/jpkinventory-data/inventory.sqlite3"
# Set ADMIN_PASSWORD securely before the first start; use COOKIE_SECURE=1 for HTTPS.
export COOKIE_SECURE=0
.venv/bin/gunicorn 'backend.app:create_app()' --bind 127.0.0.1:8084 \
  --workers 2 --threads 4 --timeout 30
```

Run from the repository root. Native Gunicorn does not automatically load the
Compose `.env`: provide `DATABASE_PATH`, `ADMIN_PASSWORD`, and `COOKIE_SECURE`
through the process environment or a protected service-manager environment
file. Run under an unprivileged service account that owns the data directory,
configure a service manager to restart it, and place an HTTPS reverse proxy in
front for remote access. Bind to the private address instead of loopback only
when direct LAN access is intended. Do not use `backend.dev` or
`scripts/serve.py` as a production server; the latter serves static files only.
For native maintenance, use `python3 -m backend.manage check` and
`python3 -m backend.manage backup /absolute/path/to/new-backup.sqlite3` with the
same `DATABASE_PATH` environment and service-account permissions.

### Updates and recovery

Before an update, create and verify a database backup using the **Backup /
Restore** section. Preserve `.env` and `DATA_DIR`, review local modifications,
pull with `git pull --ff-only origin main`, regenerate `index.html`, and run
`docker compose up -d --build --wait` (or restart the native service after updating
its dependencies). Check container health, login and an existing inventory
record. SQLite backups contain login accounts and sessions as well as inventory;
keep them private. Restoring an older backup also restores the account state at
that time, including its passwords. Never commit `.env` or runtime data to Git.
