# Week of Design: VPS applications & review desk

This repository keeps the original Arabic editorial landing page intact on GitHub Pages and adds an independent, production-ready **FastAPI + SQLite** intake service for a Hostinger VPS. The service serves the same `index.html` and `assets/` on an isolated host, plus application forms and the private review desk.

## User experience

- `https://DESIGNWEEK_DOMAIN/` — Arabic reference website, same visual palette, SVG illustrations, programme and principles.
- `https://DESIGNWEEK_DOMAIN/apply/` — six participation types: artist, maker/vendor, workshop, venue, resources, crew.
- `https://DESIGNWEEK_DOMAIN/apply/artist/` etc. — tailored Arabic form for each category (includes optional portfolio upload).
- `https://DESIGNWEEK_DOMAIN/manage/login/` — authenticated coordinator access.
- `/manage/` — private review queue, filters by category/status, details, status notes, and CSV export.
- `/privacy/` — privacy explanation.

All personal data and uploaded files are stored exclusively in a Docker volume containing SQLite and a **private** upload directory. Uploads are not served as public static files; a staff login is required to download them. No records go to public GitHub.

## Deployment model — never replace other hosted sites

This application exposes only **127.0.0.1:8926** on the VPS, so it cannot conflict with Hub Suite, other sites, or existing reverse proxies. Point a **new** HTTPS host/subdomain at the VPS and proxy its virtual host to `http://127.0.0.1:8926`. Do not overwrite another site's DNS or Nginx configuration. Use `deploy/nginx-site.example.conf` *inside a new matching SSL server block*; DNS and certificate must be configured separately. TLS must be enabled before accepting applications or signing in.

1. Ensure Docker Engine + Compose plugin, Git and your preferred reverse proxy are available.
2. From a VPS login with Docker access: `mkdir -p ~/apps && git clone https://github.com/Maximad/DesignWeek.git ~/apps/designweek && cd ~/apps/designweek`.
3. `cp .env.example .env && chmod 600 .env` — replace every placeholder privately. Generate `DW_SECRET_KEY` with `python3 -c 'import secrets;print(secrets.token_urlsafe(48))'`. Generate admin verifier with `python -m server.hash_password` in an environment with Python dependencies installed (or follow the PBKDF2 algorithm in the script); **never put plaintext password or secrets in GitHub**.
4. Set `DW_ALLOWED_HOSTS` to the exact public host; leave `DW_APPLICATIONS_OPEN=0` until HTTPS and the admin console have been verified. `DW_SECURE_COOKIES=1` must stay enabled.
5. `bash deploy/vps-deploy.sh`. Check `curl -fsS http://127.0.0.1:8926/healthz`.
6. Set up a **separate** TLS reverse proxy vhost for the chosen domain, and verify homepage, six `/apply/.../` paths and `/manage/login/` over HTTPS. Test a submission, review/download the private attachment, and remove the test record from the private database through an approved operations procedure.
7. After verification only, change `DW_APPLICATIONS_OPEN=1` in the **private VPS** `.env` and run `docker compose up -d` to restart with that setting. The homepage then dynamically replaces its static disabled links with active HTTPS category URLs; GitHub Pages remains closed until its public config is pointed to the verified VPS URLs.

The VPS service uses no external forms vendors. It is completely independent of Hub Suite and Habaq finances.

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