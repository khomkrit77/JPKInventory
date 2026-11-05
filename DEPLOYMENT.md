# Deployment verification — 2026-11-02 (Asia/Bangkok)

Server: `cm-ubuntu22`, SSH user `superuser`, repository `/home/superuser/apps/JPKInventory`, branch `main`. Working tree was clean at starting commit `e1b4d4e`. No backend, server database, or Docker mount existed previously: Nginx served static HTML; the application used browser localStorage. New record handlers depended on `crypto.randomUUID()` and failed at insecure HTTP origins.

Implemented a same-origin Python/Gunicorn API and SQLite database for users, devices, sites, services and issues. Saves wait for database confirmation. SQLite schema migration is additive and transactional; incoming legacy schema 1/2 data is validated and merged without overwriting differing records with the same ID. A stale revision returns HTTP 409. Sites now support edits and deletion of unreferenced sites; HQ is protected.

Persistent storage:

- Host: `/home/superuser/jpkinventory-data/inventory.sqlite3`
- Bind mount: `/home/superuser/jpkinventory-data` → `/data`
- Directory owner: `1000:1000` (`superuser`), mode `0700`
- App runtime UID/GID: `1000:1000`, non-root; image default remains `10001:10001`
- Host port `0.0.0.0:8084` → app `8080`
- `.env` stays on server with mode `0600`, outside Git

Verified:

- Unit/integration tests cover every collection, relationships, concurrent writes, stale revisions, validation errors, schema reopen, legacy import conflicts, backup and restore.
- Chrome on the real server through an SSH tunnel: create/edit Users, Devices, Sites, Issues; read from a separate browser session; no JavaScript errors.
- Insecure HTTP test confirmed `isSecureContext=false` and `crypto.randomUUID=undefined`; saving succeeded with the new UUID fallback.
- Rebuilt/recreated only `inventory`; all data and revision matched the pre-recreate snapshot exactly.
- UI deletion preserves issue reporter/target names; deleting referenced sites is blocked.
- UI export/import of a schema-1 localStorage fixture succeeded and left the browser's original key unchanged.
- Conflicting edits in independent browser sessions were rejected without overwriting the other user's save.
- QA records were removed using the UI after verification.
- Container healthy, SQLite `integrity_check=ok`, foreign key check empty, no final startup errors.

Backups created on server:

- `/home/superuser/jpkinventory-backups/pre-database-source.tar.gz`: source before deployment
- `/home/superuser/jpkinventory-data/backups/before-recreate.sqlite3`: verified database backup before persistence test
- Subsequent database backups are kept under `/home/superuser/jpkinventory-data/backups/`

See README for online backup, restore with app stopped, and browser localStorage export/import. Existing browser data cannot be read remotely and has not been silently imported or deleted. Keep the original browser/profile/origin until its JSON export is saved.

Network limitation: the server itself serves HTTP on port 8084. Testing `http://27.254.185.87:8084` from the client returned an `SSH-2.0-OpenSSH_8.9p1` banner, not HTTP. Direct access to LAN `192.168.11.100:8084` from the test client timed out. Public access needs the correct public IP/domain and a verified TCP 8084 route/NAT to `192.168.11.100:8084`. Do not replace a live SSH mapping without another confirmed management path. `ufw status` requires sudo authentication unavailable to this session; no firewall or NAT rules were changed.

Test URLs: server-local `http://127.0.0.1:8084`; LAN `http://192.168.11.100:8084` when network routing allows. Public URL remains unverified pending network clarification. The authentication update below adds local login accounts and API permission checks.

### Authentication update

Rebuild/restart the service to apply the login and user-management changes:
`docker compose up -d --build`. The existing SQLite database gets separate account
and session tables automatically; inventory data is preserved. Sign in as `admin`
using `ADMIN_PASSWORD` (default `JpkAdmin2026`) and change the password when prompted.
This setting seeds only the initial account and does not reset existing passwords.
For HTTPS deployments, set `COOKIE_SECURE=1` in `.env` before recreating the service.
