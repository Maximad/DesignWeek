# Week of Design: VPS applications & review desk

This repository keeps the original Arabic editorial landing page intact on GitHub Pages and adds an independent, production-ready **FastAPI + SQLite** intake service for a Hostinger VPS. The service serves the same `index.html` and `assets/` on an isolated host, plus application forms and the private review desk.

## Canonical project address — designweek.nass.life (deployment pending)

**Chosen hostname:** `designweek.nass.life` for the public Arabic catalogue, six application forms, and private coordinator review desk. The previously documented Hostinger VPS is `srv1169365`, last reported at public IPv4 **72.62.52.167** (14 November 2026). Confirm this VPS address and the current DNS zone before updating anything; no live DNS or SSH access was available during this ChatGPT run.

**Only DNS change required:** create `A designweek.nass.life → 72.62.52.167` with TTL 300 seconds or the Hostinger default. First inspect `designweek` A/AAAA/CNAME for conflicts, and read the current `nass.life` zone/snapshot. Leave `@`, `www`, `hub`, MX, TXT (including SPF/DKIM/DMARC), verification and other service DNS records unchanged. Never change domain nameservers to do this. The Hostinger DNS zone was previously used to add `hub.nass.life`.

**Reverse proxy:** the actual VPS gateway runs **Caddy** in a container, not a host-level Nginx instance. Therefore use the isolated `deploy/Caddyfile.designweek.nass.life.example` route and `deploy/compose.gateway.example.yml` overlay after discovering the gateway's *actual shared Docker network*. Caddy issues HTTPS certificates automatically once DNS resolves and inbound ports 80/443 are working. Do not replace an existing Caddyfile; add one site block and validate/reload the existing gateway. Do not expose private application data or another service through this hostname.

**Cutover:** GitHub Pages `https://maximad.github.io/DesignWeek/` remains available and continues to disable submission buttons. Do not announce the new host or open applications until `https://designweek.nass.life/` and its form/admin routes have passed actual end-to-end HTTPS tests.

## User experience

- `https://designweek.nass.life/` — Arabic reference website, same visual palette, SVG illustrations, programme and principles.
- `https://designweek.nass.life/apply/` — six participation types: artist, maker/vendor, workshop, venue, resources, crew.
- `https://designweek.nass.life/apply/artist/` etc. — tailored Arabic form for each category (includes optional portfolio upload).
- `https://designweek.nass.life/manage/login/` — authenticated coordinator access.
- `/manage/` — private review queue, filters by category/status, details, status notes, and CSV export.
- `/privacy/` — privacy explanation.

All personal data and uploaded files are stored exclusively in a Docker volume containing SQLite and a **private** upload directory. Uploads are not served as public static files; a staff login is required to download them. No records go to public GitHub.

## Deployment on the existing VPS — do not replace Hub Suite or the Caddy gateway

The app has a dedicated Docker Compose project and continues to bind **127.0.0.1:8926** for a local health check. For the **existing containerized Caddy gateway**, add a second network only after inspecting the gateway's actual attached networks. Caddy cannot reach `127.0.0.1:8926` inside a separate container; it must reach `designweek:8000` over a Docker network shared with the DesignWeek container.

1. Inspect the VPS first (`srv1169365`): `docker ps --format '{{.Names}} {{.Ports}}'`, `docker inspect gateway-caddy-1 --format '{{json .NetworkSettings.Networks}}'`, and check whether ports **80/443** are already handled by Caddy. Do not start another proxy. Ensure no existing Caddy route claims `designweek.nass.life`.
2. Check `nass.life` DNS and create only the `designweek` **A → 72.62.52.167** record after live address verification; leave unrelated records untouched.
3. Clone: `mkdir -p ~/apps && git clone https://github.com/Maximad/DesignWeek.git ~/apps/designweek && cd ~/apps/designweek`.
4. Create private credentials: `cp .env.example .env && chmod 600 .env`. Replace all placeholders with secrets generated *on the VPS*: `DW_SECRET_KEY` (48+ random bytes) and `DW_ADMIN_PASSWORD_HASH` (generated using `python -m server.hash_password`). Keep `DW_ALLOWED_HOSTS=designweek.nass.life`, `DW_APPLICATIONS_OPEN=0`, `DW_SECURE_COOKIES=1`. Do not commit secrets.
5. Determine an **existing** Docker bridge network to which `gateway-caddy-1` is connected. Set `DW_GATEWAY_NETWORK=ACTUAL_CADDY_NETWORK` in private `.env`. Copy the opt-in overlay: `cp deploy/compose.gateway.example.yml compose.gateway.yml`. The deploy script automatically includes it if present. No other container is modified.
6. Deploy: `bash deploy/vps-deploy.sh`. Check `curl -fsS http://127.0.0.1:8926/healthz`. Before editing Caddy, test internal reachability from the shared network. If the gateway is not on the chosen network, stop and inspect rather than connecting it blindly.
7. Add the **new** `designweek.nass.life` site block from `deploy/Caddyfile.designweek.nass.life.example` to the existing gateway Caddyfile beneath `/opt/gateway` using its actual current deployment layout. Validate and reload the existing Caddy process without replacing the configuration of Hub Suite, AzuraCast, other services or `work.habaq.online`. Let Caddy issue TLS after DNS resolves.
8. Verify the live site over HTTPS, all six `/apply/...` categories, `/privacy/`, `/manage/login/`, access-controlled downloads, a test submission and response management. Confirm TLS and HTTP→HTTPS redirect.
9. Only after security and access checks: set `DW_APPLICATIONS_OPEN=1` in the private VPS `.env`; run `bash deploy/vps-deploy.sh` again and verify form submission. The public site served by the VPS will then activate its category links; the old GitHub Pages site will stay closed until redirected or linked explicitly.

Do not reuse another app's database, upload folder, admin session, gateway credentials or TLS certificates. The DesignWeek data volume remains separate from Hub and Habaq.

## Update & rollback

- Update: `bash deploy/vps-deploy.sh` from VPS (fast-forward only; never force-reset).
- Database and uploads live in the `designweek_private_data` named Docker volume: they survive container rebuilds and Git pulls.
- Backup: `bash deploy/backup.sh` on the VPS; this makes a SQLite-consistent backup and includes private attachments. Copy encrypted backups offsite according to the team's retention policy.
- Roll back code by checking out a known tested commit and rebuilding via Docker Compose; **do not** roll back the database without matching migration and backup review. Schema changes need explicit migrations.

## GitHub Actions

`.github/workflows/backend-ci.yml` tests the application on pull requests. `.github/workflows/vps-deploy.yml` is deliberately **manual** and refuses deployment unless the four GitHub VPS SSH secrets are configured and the server already has a valid private `.env`. It does not provision a VPS or alter other sites.

The Hostinger integration used in the current ChatGPT session did not expose VPS control or SSH capabilities. That prevents verifying the server/host and performing an actual deployment from chat in this run; the code has been prepared and tested without pretending a VPS is live.

## Security and operations

- Login uses PBKDF2-HMAC-SHA256, an 8-hour signed session, secure and SameSite cookies, and CSRF tokens on state-changing routes.
- Uploaded files: at most 8MB each, PDF/JPG/PNG/WebP only, signature checked; private UUID naming; no public serving.
- Honeypot and per-contact application rate limit; max reverse-proxy request body 10MB.
- Application statuses: new, review, clarification, accepted, waitlist, declined, withdrawn.
- Admin CSV export guards against spreadsheet formula injection.
- Admin requests set `Cache-Control: no-store`; response headers prevent content sniffing, framing and third-party embeds.
- Maintain an offsite backup, limited staff access, privacy retention schedule and a server update routine. These still need operational ownership.