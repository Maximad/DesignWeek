"""Arabic DesignWeek applications and a small private review desk.

Static public site is served from the repository root. Personal data and uploads
stay in a private SQLite-backed volume, never in GitHub or public static paths.
"""
from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from .site_content import all_fields, field_groups
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = Path(os.getenv("DW_DATA_DIR", "/data"))
DB = PRIVATE / "applications.sqlite3"
UPLOADS = PRIVATE / "private-uploads"
PUBLIC = ROOT / "assets"
TEMPLATES = Path(__file__).resolve().parent / "templates"
SECRET = os.getenv("DW_SECRET_KEY", "")
ADMIN_USER = os.getenv("DW_ADMIN_USERNAME", "admin")
ADMIN_HASH = os.getenv("DW_ADMIN_PASSWORD_HASH", "")
APPLICATIONS_OPEN = os.getenv("DW_APPLICATIONS_OPEN", "0") == "1"
MAX_UPLOAD = 8 * 1024 * 1024
CATEGORIES = {
    "artist": ("عرض عمل فني", "وصف المواد والأبعاد وطريقة العرض", "متطلبات التركيب والنقل وحماية العمل"),
    "maker": ("سوق التصميم", "أنواع المنتجات وأسعارها التقريبية", "المساحة أو الطاولة والتجهيزات المطلوبة"),
    "workshop": ("ورشة أو حوار", "المدة والسعة والفئة المستهدفة", "المواد والتكلفة وإجراءات السلامة"),
    "space": ("مساحة ثقافية", "عنوان المساحة وسعتها وتجهيزاتها", "برنامج الاستضافة ومسؤول التشغيل"),
    "partner": ("مساهمة أو دعم", "نوع الموارد أو الخدمات المقدمة", "شروط الاستخدام أو الاعتراف المقترحة"),
    "crew": ("فريق التنظيم", "المهارات والخبرة المناسبة", "الأيام والساعات المتاحة والمهام المفضلة"),
}
STATUSES = {
    "new": "جديد", "review": "قيد المراجعة", "clarify": "استيضاح", "accepted": "مقبول",
    "waitlist": "قائمة انتظار", "declined": "غير مقبول", "withdrawn": "منسحب",
}
FILE_SIGNATURES = {
    ".pdf": (b"%PDF-",), ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",),
    ".webp": (b"RIFF",),
}
app = FastAPI(title="DesignWeek Applications", docs_url=None, redoc_url=None, openapi_url=None)
_hosts = [host.strip() for host in os.getenv("DW_ALLOWED_HOSTS", "").split(",") if host.strip()]
if _hosts:
    _hosts.extend(["localhost", "127.0.0.1"])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_hosts)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = ("default-src 'self'; img-src 'self' data:; "
      "script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
      "font-src 'self' https://fonts.gstatic.com; object-src 'none'; "
      "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
    if request.url.path.startswith("/manage/"):
        response.headers["Cache-Control"] = "no-store"
    return response
app.add_middleware(SessionMiddleware, secret_key=SECRET or secrets.token_urlsafe(32), https_only=os.getenv("DW_SECURE_COOKIES", "1") == "1", same_site="lax", max_age=8*60*60)
app.mount("/assets", StaticFiles(directory=str(PUBLIC), check_dir=False), name="assets")
app.mount("/server-static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="server-static")
tpl = Jinja2Templates(directory=str(TEMPLATES))
csrf_serializer = URLSafeTimedSerializer(SECRET or secrets.token_urlsafe(32), salt="designweek-csrf")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db() -> None:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    UPLOADS.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS applications (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, category TEXT NOT NULL,
            full_name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL,
            city TEXT NOT NULL, project_title TEXT NOT NULL, description TEXT NOT NULL,
            portfolio_url TEXT NOT NULL, availability TEXT NOT NULL, needs TEXT NOT NULL,
            extra_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new', notes TEXT NOT NULL DEFAULT '',
            file_path TEXT, file_name TEXT, file_type TEXT, file_size INTEGER NOT NULL DEFAULT 0)""")
        db.execute("CREATE INDEX IF NOT EXISTS ix_app_created ON applications(created_at)")
        db.execute("CREATE INDEX IF NOT EXISTS ix_app_status ON applications(status, category)")
        db.execute("""CREATE TABLE IF NOT EXISTS site_content (
            key TEXT PRIMARY KEY, value TEXT NOT NULL, changed_at TEXT NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS limits (
            token TEXT PRIMARY KEY, start_epoch INTEGER NOT NULL, count INTEGER NOT NULL)""")
        db.commit()


@contextmanager
def connect():
    db = sqlite3.connect(str(DB), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=10000")
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def startup():
    if os.getenv("DW_ENV", "production") == "production":
        if not SECRET or len(SECRET) < 32 or not ADMIN_HASH:
            raise RuntimeError("Set DW_SECRET_KEY (32+ chars) and DW_ADMIN_PASSWORD_HASH before starting production")
    init_db()


def render(request: Request, name: str, **extra):
    data = {"request": request, "categories": CATEGORIES, "statuses": STATUSES, "open": APPLICATIONS_OPEN}
    data.update(extra)
    return tpl.TemplateResponse(request, name, data)


def token_for(action: str) -> str:
    return csrf_serializer.dumps(action)


def require_csrf(token: str, action: str) -> None:
    try:
        if csrf_serializer.loads(token, max_age=8*3600) != action:
            raise ValueError("csrf mismatch")
    except (BadSignature, SignatureExpired, ValueError):
        raise HTTPException(403, "Invalid or expired request token")


def authenticated(request: Request) -> bool:
    return request.session.get("dw_admin") == ADMIN_USER and bool(ADMIN_HASH)


def require_admin(request: Request) -> None:
    if not authenticated(request):
        raise HTTPException(403, "Administrator sign-in required")


def check_admin_password(password: str) -> bool:
    try:
        method, iterations, salt, expected = ADMIN_HASH.split(":", 3)
        if method != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def rate_limit(identity: str) -> None:
    key = hmac.new((SECRET or "test").encode(), identity.strip().lower().encode(), "sha256").hexdigest()
    now = int(time.time())
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT start_epoch, count FROM limits WHERE token=?", (key,)).fetchone()
        if row and now - row["start_epoch"] < 3600:
            if row["count"] >= 5:
                raise HTTPException(429, "تم بلوغ حد الطلبات لهذا الحساب. حاول لاحقاً.")
            db.execute("UPDATE limits SET count=count+1 WHERE token=?", (key,))
        else:
            db.execute("INSERT OR REPLACE INTO limits(token,start_epoch,count) VALUES (?,?,1)", (key, now))
        db.commit()


def validate_upload_name(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext not in FILE_SIGNATURES:
        raise ValueError("الملفات المسموحة: PDF وJPG وPNG وWEBP فقط")
    return ext


async def save_file(file: UploadFile | None, uid: str):
    if not file or not file.filename:
        return None, None, None, 0
    extension = validate_upload_name(file.filename)
    dest = UPLOADS / f"{uid}{extension}"
    size = 0
    first = b""
    try:
        with dest.open("xb") as out:
            while True:
                block = await file.read(128 * 1024)
                if not block:
                    break
                if not first:
                    first = block[:16]
                size += len(block)
                if size > MAX_UPLOAD:
                    raise ValueError("الحد الأقصى للملف 8 ميغابايت")
                out.write(block)
        if not any(first.startswith(sig) for sig in FILE_SIGNATURES[extension]):
            raise ValueError("نوع الملف لا يطابق امتداده")
        if extension == ".webp" and first[8:12] != b"WEBP":
            raise ValueError("ملف WEBP غير صالح")
        return dest.name, Path(file.filename).name[:160], extension, size
    except Exception:
        dest.unlink(missing_ok=True)
        raise


@app.get("/", include_in_schema=False)
def home():
    # The existing GitHub Pages copy stays closed. On the HTTPS VPS the same
    # catalogue gets real, category-specific links to the private intake.
    doc = (ROOT / "index.html").read_text(encoding="utf-8")
    doc = doc.replace('<script defer src="./assets/site-config.js"></script>',
                      '<script defer src="./runtime-config.js"></script>\n  <script defer src="./content-config.js"></script>')
    if APPLICATIONS_OPEN:
        doc = doc.replace("طلبات المشاركة الإلكترونية ستُفتح لاحقاً", "طلبات المشاركة الإلكترونية مفتوحة الآن")
        doc = doc.replace("حتى ذلك الحين، يمكنك معرفة ما يتطلبه كل نوع من المشاركات وتحضير وصف مشروعك وأعمالك. لا تُجمع أي بيانات شخصية عبر هذه الصفحة حالياً.",
                          "اختر نوع المشاركة، راجع المعلومات المطلوبة، ثم انتقل إلى استمارة التقديم. تُحفظ الطلبات بشكل خاص للمراجعة.")
        doc = doc.replace("سنوضح لك المعلومات الأساسية المطلوبة للبدء، ثم نضيف رابط التقديم الإلكتروني عند تفعيله.",
                          "اختر نوع المشاركة لمعرفة المعلومات المطلوبة ثم انتقل إلى الاستمارة الإلكترونية.")
        doc = doc.replace("نسخة تعريفية قابلة للتحديث — لم تُفتح الطلبات الإلكترونية بعد.",
                          "طلبات المشاركة الإلكترونية مفتوحة الآن.")
    return HTMLResponse(doc, headers={"Cache-Control": "no-store"})


@app.get("/content-config.js", include_in_schema=False)
def public_content():
    allowed = {field["key"] for field in all_fields()}
    with connect() as db:
        values = {row["key"]: row["value"] for row in db.execute("SELECT key,value FROM site_content") if row["key"] in allowed}
    payload = json.dumps(values, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return Response("window.HUB_DESIGN_WEEK_CONTENT = Object.freeze(" + payload + ");", media_type="application/javascript", headers={"Cache-Control": "no-store"})


@app.get("/runtime-config.js", include_in_schema=False)
def runtime_config(request: Request):
    origin = str(request.base_url).rstrip("/")
    if not origin.startswith("https://"):
        enabled = False
    else:
        enabled = APPLICATIONS_OPEN
    urls = {slug: f"{origin}/apply/{slug}/" if enabled else None for slug in CATEGORIES}
    script = "window.HUB_DESIGN_WEEK_CONFIG = Object.freeze(" + json.dumps({
        "applicationsOpen": enabled, "formUrls": urls}, ensure_ascii=False) + ");"
    return Response(script, media_type="application/javascript", headers={"Cache-Control": "no-store"})


@app.get("/healthz", include_in_schema=False)
def health():
    with connect() as db:
        db.execute("SELECT 1")
    return {"status": "ok", "service": "designweek"}


@app.get("/apply/", response_class=HTMLResponse)
def apply_index(request: Request):
    return render(request, "apply-index.html")


@app.get("/apply/{category}/", response_class=HTMLResponse)
def application_form(request: Request, category: str):
    if category not in CATEGORIES:
        raise HTTPException(404)
    return render(request, "apply-form.html", category=category, csrf=token_for("apply:"+category), error=None, values={})


@app.post("/apply/{category}/", response_class=HTMLResponse)
async def application_submit(request: Request, category: str,
    full_name: str = Form(""), email: str = Form(""), phone: str = Form(""), city: str = Form(""),
    project_title: str = Form(""), description: str = Form(""), portfolio_url: str = Form(""),
    availability: str = Form(""), needs: str = Form(""), extra_1: str = Form(""), extra_2: str = Form(""),
    consent: str = Form(""), terms: str = Form(""), csrf: str = Form(""), website: str = Form(""),
    portfolio_file: UploadFile | None = File(None)):
    if category not in CATEGORIES:
        raise HTTPException(404)
    if not APPLICATIONS_OPEN:
        return render(request, "apply-form.html", category=category, csrf=token_for("apply:"+category), error="استقبال الطلبات غير مفتوح حالياً", values={})
    require_csrf(csrf, "apply:"+category)
    if website:  # honeypot: act as successful submission for bots but store nothing
        return render(request, "thanks.html", reference="—")
    vals = locals().copy()
    fields = ["full_name", "email", "phone", "city", "project_title", "description", "portfolio_url", "availability", "needs", "extra_1", "extra_2"]
    info = {key: str(vals[key]).strip() for key in fields}
    error = None
    if len(info["full_name"]) < 2 or len(info["full_name"]) > 120:
        error = "يرجى كتابة الاسم (من 2 إلى 120 حرفاً)"
    elif not (info["email"] or info["phone"]):
        error = "يرجى إضافة بريد إلكتروني أو رقم هاتف للتواصل"
    elif info["email"] and (len(info["email"]) > 200 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", info["email"])):
        error = "صيغة البريد الإلكتروني غير صحيحة"
    elif len(info["phone"]) > 80 or len(info["city"]) > 120:
        error = "أحد الحقول أطول من المسموح"
    elif not 3 <= len(info["project_title"]) <= 180:
        error = "يرجى إدخال عنوان المشروع أو فكرة المشاركة"
    elif not 30 <= len(info["description"]) <= 2500:
        error = "يرجى وصف الفكرة بما لا يقل عن 30 حرفاً ولا يزيد عن 2500 حرف"
    elif any(len(info[k]) > 2000 for k in ["availability", "needs", "extra_1", "extra_2"]):
        error = "أحد حقول التفاصيل أطول من المسموح"
    elif info["portfolio_url"] and (len(info["portfolio_url"]) > 500 or not re.match(r"^https?://[^\s]+$", info["portfolio_url"], flags=re.I)):
        error = "يرجى استخدام رابط أعمال يبدأ بـ https:// أو http://"
    elif consent != "yes" or terms != "yes":
        error = "يجب الموافقة على شروط التواصل والإرسال"
    if error:
        return render(request, "apply-form.html", category=category, csrf=token_for("apply:"+category), error=error, values=info)
    rate_limit(info["email"] or info["phone"])
    uid = uuid.uuid4().hex
    try:
        path, name, ftype, length = await save_file(portfolio_file, uid)
    except ValueError as e:
        return render(request, "apply-form.html", category=category, csrf=token_for("apply:"+category), error=str(e), values=info)
    try:
        with connect() as db:
            db.execute("""INSERT INTO applications(id,created_at,category,full_name,email,phone,city,project_title,
                description,portfolio_url,availability,needs,extra_json,status,file_path,file_name,file_type,file_size)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'new',?,?,?,?)""",
                (uid, utcnow(), category, info["full_name"], info["email"], info["phone"], info["city"],
                 info["project_title"], info["description"], info["portfolio_url"], info["availability"],
                 info["needs"], json.dumps({"extra_1": info["extra_1"], "extra_2": info["extra_2"]}, ensure_ascii=False),
                 path, name, ftype, length))
            db.commit()
    except Exception:
        if path:
            (UPLOADS / path).unlink(missing_ok=True)
        raise
    return render(request, "thanks.html", reference=uid[:10].upper())


@app.get("/privacy/", response_class=HTMLResponse)
def privacy(request: Request):
    return render(request, "privacy.html")


@app.get("/manage/content/", response_class=HTMLResponse)
def edit_site_content(request: Request, section: str = "", saved: str = ""):
    if not authenticated(request):
        return RedirectResponse("/manage/login/", status_code=303)
    groups = field_groups()
    if section not in groups:
        section = next(iter(groups), "")
    with connect() as db:
        overrides = {row["key"]: row["value"] for row in db.execute("SELECT key,value FROM site_content")}
    def section_url(name: str) -> str:
        if name.startswith("البرنامج"): return "/#program"
        if name.startswith("تفاصيل المشاركة") or name == "المشاركة": return "/#participate"
        return {
            "مقدمة الأسبوع": "/", "التنقل": "/", "دليل الموقع": "/",
            "تعريف الأسبوع": "/#about", "المبادئ والقيم": "/#about",
            "المحاور الفنية": "/#tracks", "المكان": "/#place",
            "معايير الاختيار": "/#standards", "الرؤية المستقبلية": "/#future",
            "الأسئلة الشائعة": "/#faq", "الدعوة الختامية": "/#future",
            "التذييل": "/",
        }.get(name, "/")
    return render(
        request, "content-editor.html", groups=groups, overrides=overrides,
        active=section, saved=saved == "1", csrf=token_for("content:" + section),
        preview_links={name: section_url(name) for name in groups},
    )


@app.post("/manage/content/")
async def save_site_content(request: Request):
    require_admin(request)
    form = await request.form()
    section = str(form.get("section", ""))
    groups = field_groups()
    if section not in groups:
        raise HTTPException(400, "Unknown content section")
    require_csrf(str(form.get("csrf", "")), "content:" + section)
    changes = []
    for field in groups[section]:
        key = field["key"]
        value = str(form.get(key, "")).strip()
        if len(value) > 2500 or any(c in value for c in ("\\x00", "\\x1b")):
            raise HTTPException(400, "Content is too long or contains prohibited characters")
        changes.append((key, value if value and value != field["default"] else None))
    with connect() as db:
        for key, value in changes:
            if value is None:
                db.execute("DELETE FROM site_content WHERE key=?", (key,))
            else:
                db.execute(
                    "INSERT INTO site_content(key,value,changed_at) VALUES(?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value,changed_at=excluded.changed_at",
                    (key, value, utcnow()),
                )
        db.commit()
    return RedirectResponse("/manage/content/?" + urlencode({"section": section, "saved": "1"}), status_code=303)


@app.get("/manage/login/", response_class=HTMLResponse)
def login(request: Request):
    if authenticated(request):
        return RedirectResponse("/manage/", status_code=303)
    return render(request, "login.html", csrf=token_for("login"), error=None, admin_username=ADMIN_USER)


@app.post("/manage/login/", response_class=HTMLResponse)
async def login_post(request: Request, username: str = Form(""), password: str = Form(""), csrf: str = Form("")):
    require_csrf(csrf, "login")
    if hmac.compare_digest(username, ADMIN_USER) and check_admin_password(password):
        request.session["dw_admin"] = ADMIN_USER
        return RedirectResponse("/manage/", status_code=303)
    return render(request, "login.html", csrf=token_for("login"), error="معلومات الدخول غير صحيحة", admin_username=ADMIN_USER)


@app.post("/manage/logout/")
async def logout(request: Request, csrf: str = Form("")):
    require_admin(request)
    require_csrf(csrf, "manage")
    request.session.clear()
    return RedirectResponse("/manage/login/", status_code=303)


@app.get("/manage/", response_class=HTMLResponse)
def dashboard(request: Request, status: str = "", category: str = ""):
    if not authenticated(request):
        return RedirectResponse("/manage/login/", status_code=303)
    if status not in STATUSES:
        status = ""
    if category not in CATEGORIES:
        category = ""
    sql = "SELECT id,created_at,category,full_name,email,phone,project_title,status FROM applications WHERE 1=1"
    params = []
    if status:
        sql += " AND status=?"; params.append(status)
    if category:
        sql += " AND category=?"; params.append(category)
    sql += " ORDER BY created_at DESC LIMIT 1000"
    with connect() as db:
        rows = [dict(row) for row in db.execute(sql, params)]
        total = db.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    return render(request, "dashboard.html", rows=rows, total=total, status_filter=status, category_filter=category, csrf=token_for("manage"))


@app.get("/manage/application/{uid}/", response_class=HTMLResponse)
def detail(request: Request, uid: str):
    if not authenticated(request):
        return RedirectResponse("/manage/login/", status_code=303)
    with connect() as db:
        row = db.execute("SELECT * FROM applications WHERE id=?", (uid,)).fetchone()
    if not row:
        raise HTTPException(404)
    item = dict(row); item["extra"] = json.loads(item["extra_json"])
    return render(request, "detail.html", item=item, csrf=token_for("manage"))


@app.post("/manage/application/{uid}/")
async def update_detail(request: Request, uid: str, status: str = Form(""), notes: str = Form(""), csrf: str = Form("")):
    require_admin(request)
    require_csrf(csrf, "manage")
    if status not in STATUSES:
        raise HTTPException(400, "Invalid status")
    with connect() as db:
        cur = db.execute("UPDATE applications SET status=?, notes=? WHERE id=?", (status, notes[:5000], uid))
        db.commit()
    if cur.rowcount == 0:
        raise HTTPException(404)
    return RedirectResponse("/manage/application/"+uid+"/", status_code=303)


@app.get("/manage/file/{uid}/")
def download(request: Request, uid: str):
    require_admin(request)
    with connect() as db:
        row = db.execute("SELECT file_path,file_name FROM applications WHERE id=?", (uid,)).fetchone()
    if not row or not row["file_path"]:
        raise HTTPException(404)
    path = UPLOADS / Path(row["file_path"]).name
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, filename=row["file_name"], media_type="application/octet-stream")


def csv_safe(value: object) -> str:
    text = str(value if value is not None else "")
    if text.lstrip().startswith(("=", "+", "-", "@")) or "\r" in text or "\n" in text or "\t" in text:
        return "'"+text
    return text


@app.get("/manage/export.csv")
def export_csv(request: Request):
    require_admin(request)
    out = io.StringIO()
    writer = csv.writer(out)
    fields = ["id", "created_at", "category", "full_name", "email", "phone", "city", "project_title", "description", "portfolio_url", "availability", "needs", "status", "notes"]
    writer.writerow(fields)
    with connect() as db:
        for row in db.execute("SELECT "+",".join(fields)+" FROM applications ORDER BY created_at DESC"):
            writer.writerow([csv_safe(row[f]) for f in fields])
    return Response("\ufeff"+out.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=designweek-applications.csv", "Cache-Control": "no-store"})