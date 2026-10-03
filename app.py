import os, re, sqlite3, hmac, secrets, time, threading, urllib.request, json, smtplib, ssl, hashlib
from datetime import datetime
from functools import wraps
from flask import Response, send_file, Flask, g, render_template, request, redirect, url_for, session, abort, jsonify
from markupsafe import Markup
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash
from email.message import EmailMessage
from xml.sax.saxutils import escape
import markdown, bleach

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("DB_PATH", os.path.join(BASE, "data", "vlogs.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1",   # set COOKIE_SECURE=1 once you are on HTTPS
                  MAX_CONTENT_LENGTH=12 * 1024 * 1024)
LOGIN_PATH = os.environ.get("ADMIN_LOGIN_PATH", "/signin")   # unlisted: no page links to it

TAGS = list(bleach.sanitizer.ALLOWED_TAGS) + ["p", "pre", "h1", "h2", "h3", "h4", "img", "br", "hr",
        "ul", "ol", "li", "table", "thead", "tbody", "tr", "th", "td"]
ATTRS = {**bleach.sanitizer.ALLOWED_ATTRIBUTES, "img": ["src", "alt"], "code": ["class"]}

def render_md(text):
    html = markdown.markdown(text or "", extensions=["fenced_code", "tables"])
    return Markup(bleach.clean(html, tags=TAGS, attributes=ATTRS))
app.jinja_env.filters["md"] = render_md

def db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DB), exist_ok=True)
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("""CREATE TABLE IF NOT EXISTS vlogs(id INTEGER PRIMARY KEY, slug TEXT UNIQUE,
            title TEXT, summary TEXT, body TEXT, published INTEGER DEFAULT 1, created TEXT, updated TEXT)""")
    return g.db

@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d: d.close()

def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "vlog"

@app.context_processor
def inject():
    session.setdefault("csrf", secrets.token_hex(16))
    return {"csrf": session["csrf"], "admin": session.get("admin", False),
            "gsc": os.environ.get("GOOGLE_SITE_VERIFICATION", "")}

@app.before_request
def csrf_check():
    if request.method == "POST":
        sent = request.form.get("csrf") or request.headers.get("X-CSRF", "")
        if not hmac.compare_digest(sent, session.get("csrf", "")):
            abort(400)

def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("admin"):
            abort(404)          # visitors can't tell an admin area exists
        return f(*a, **k)
    return w

@app.get("/")
def home():
    return render_template("index.html")

for _n in ("about", "work", "experience", "skills", "contact"):
    app.add_url_rule(f"/{_n}", _n, (lambda n: lambda: render_template(f"{n}.html"))(_n))

@app.get("/robots.txt")
def robots():
    return Response(f"User-agent: *\nAllow: /\n\nSitemap: {request.url_root}sitemap.xml\n", mimetype="text/plain")

@app.get("/sitemap.xml")
def sitemap():
    base = request.url_root.rstrip("/")
    items = [(base + url_for(e), None) for e in ("home", "about", "work", "experience", "skills", "resume", "vlogs", "contact")]
    for v in db().execute("SELECT slug, updated FROM vlogs WHERE published=1").fetchall():
        items.append((base + url_for("vlog", slug=v["slug"]), v["updated"][:10]))
    body = "".join(f"<url><loc>{escape(u)}</loc>" + (f"<lastmod>{m}</lastmod>" if m else "") + "</url>" for u, m in items)
    return Response('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + body + "</urlset>", mimetype="application/xml")

@app.get("/vlogs")
def vlogs():
    rows = db().execute("SELECT * FROM vlogs WHERE published=1 ORDER BY created DESC").fetchall()
    return render_template("vlogs.html", rows=rows)

@app.get("/vlog/<slug>")
def vlog(slug):
    row = db().execute("SELECT * FROM vlogs WHERE slug=? AND (published=1 OR ?)", (slug, session.get("admin", False))).fetchone()
    if not row: abort(404)
    return render_template("vlog.html", v=row)

ADMIN_FILE = os.path.join(BASE, "data", "admin.json")   # exists only after a password reset
OTP_FILE = os.path.join(BASE, "data", "otp.json")

def password_ok(p):
    if os.path.exists(ADMIN_FILE):                      # a reset password replaces the one in .env
        try: return check_password_hash(json.load(open(ADMIN_FILE))["hash"], p)
        except Exception: return False
    pw = os.environ.get("ADMIN_PASSWORD", "")
    return bool(pw) and hmac.compare_digest(p.encode(), pw.encode())

FAILS = {}   # ip -> [count, first_failure_time]

def login():
    err = None
    ip = request.remote_addr or "?"
    c, t0 = FAILS.get(ip, (0, 0))
    if c >= 5 and time.time() - t0 < 900:
        return render_template("login.html", err="Too many attempts. Try again in 15 minutes."), 429
    if session.get("admin"):
        return redirect(url_for("admin"))
    if request.method == "POST":
        if password_ok(request.form.get("password", "")):
            FAILS.pop(ip, None)
            session.clear(); session["admin"] = True
            return redirect(url_for("admin"))
        FAILS[ip] = [c + 1, t0 if c and time.time() - t0 < 900 else time.time()]
        time.sleep(1.5)
        err = "Wrong password."
    ok = "Password updated. You can sign in now." if request.args.get("reset") else None
    return render_template("login.html", err=err, ok=ok)
app.add_url_rule(LOGIN_PATH, "login", login, methods=["GET", "POST"])

# ---- Forgot password: a 6-digit code is emailed to ADMIN_EMAIL (never to an address typed on the page) ----
FORGOT_PATH = LOGIN_PATH.rstrip("/") + "/forgot"
RESET_PATH = LOGIN_PATH.rstrip("/") + "/reset"

def _load(path):
    try: return json.load(open(path))
    except Exception: return {}

def _save(path, data):
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(tmp, "w")); os.chmod(tmp, 0o600); os.replace(tmp, path)

def _otp_hash(code):
    return hmac.new(app.secret_key.encode(), code.encode(), hashlib.sha256).hexdigest()

def mail_configured():
    return all(os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "ADMIN_EMAIL"))

def send_mail(subject, body):
    m = EmailMessage()
    m["Subject"], m["From"], m["To"] = subject, os.environ["SMTP_USER"], os.environ["ADMIN_EMAIL"]
    m.set_content(body)
    host, port, ctx = os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587")), ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=15, context=ctx) as srv:
            srv.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"]); srv.send_message(m)
    else:
        with smtplib.SMTP(host, port, timeout=15) as srv:
            srv.starttls(context=ctx); srv.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"]); srv.send_message(m)

def forgot():
    err = None
    if request.method == "POST":
        now = time.time()
        o = _load(OTP_FILE)
        sent = [t for t in o.get("sent", []) if now - t < 3600]
        if not mail_configured():
            err = "Email reset is not set up on this server yet."
        elif len(sent) >= 3:
            err = "Too many codes requested. Try again in an hour."
        else:
            code = f"{secrets.randbelow(10**6):06d}"
            try:
                send_mail("Your portfolio admin reset code",
                          f"Your reset code is {code}\n\nIt expires in 10 minutes. If you did not ask for it, ignore this email.")
            except Exception:
                app.logger.exception("reset email failed")
                err = "Could not send the email. Check the SMTP settings in .env."
            else:
                _save(OTP_FILE, {"h": _otp_hash(code), "exp": now + 600, "tries": 0, "sent": sent + [now]})
                return redirect(url_for("reset"))
    return render_template("forgot.html", err=err)
app.add_url_rule(FORGOT_PATH, "forgot", forgot, methods=["GET", "POST"])

def reset():
    err = None
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        p1, p2 = request.form.get("password", ""), request.form.get("confirm", "")
        o, now = _load(OTP_FILE), time.time()
        if len(p1) < 10:
            err = "Use at least 10 characters for the new password."
        elif p1 != p2:
            err = "The two passwords do not match."
        elif not o.get("h") or now > o.get("exp", 0) or o.get("tries", 0) >= 5:
            err = "That code has expired. Request a new one."
        else:
            o["tries"] = o.get("tries", 0) + 1; _save(OTP_FILE, o)
            if not hmac.compare_digest(_otp_hash(code), o["h"]):
                err = "Wrong code."
            else:
                _save(ADMIN_FILE, {"hash": generate_password_hash(p1)})
                try: os.remove(OTP_FILE)
                except OSError: pass
                FAILS.clear(); session.clear()
                try: send_mail("Your portfolio admin password was changed", "If this was not you, sign in and change it again, and check your server.")
                except Exception: pass
                return redirect(url_for("login", reset=1))
    return render_template("reset.html", err=err)
app.add_url_rule(RESET_PATH, "reset", reset, methods=["GET", "POST"])

@app.post("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.get("/admin")
@login_required
def admin():
    rows = db().execute("SELECT * FROM vlogs ORDER BY created DESC").fetchall()
    have = os.path.exists(RESUME)
    manual = os.path.exists(MANUAL)
    src = "none yet" if not have else "uploaded by you" if manual else "synced from Google Drive" if DRIVE_ID else "the built-in copy"
    updated = datetime.fromtimestamp(os.path.getmtime(RESUME)).strftime("%d %b %Y, %H:%M") if have else None
    return render_template("admin.html", rows=rows, src=src, updated=updated, drive=bool(DRIVE_ID), manual=manual, msg=request.args.get("msg"))

@app.route("/admin/new", methods=["GET", "POST"])
@app.route("/admin/edit/<int:vid>", methods=["GET", "POST"])
@login_required
def edit(vid=None):
    d = db()
    row = d.execute("SELECT * FROM vlogs WHERE id=?", (vid,)).fetchone() if vid else None
    if vid and not row: abort(404)
    if request.method == "POST":
        f = request.form
        title = f.get("title", "").strip() or "Untitled"
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        pub = 1 if f.get("published") else 0
        if row:
            d.execute("UPDATE vlogs SET title=?, summary=?, body=?, published=?, updated=? WHERE id=?",
                      (title, f.get("summary", ""), f.get("body", ""), pub, now, vid))
            d.commit()
            return redirect(url_for("edit", vid=vid, saved=1))
        slug, n = slugify(title), 1
        while d.execute("SELECT 1 FROM vlogs WHERE slug=?", (slug,)).fetchone():
            n += 1; slug = f"{slugify(title)}-{n}"
        cur = d.execute("INSERT INTO vlogs(slug,title,summary,body,published,created,updated) VALUES(?,?,?,?,?,?,?)",
                        (slug, title, f.get("summary", ""), f.get("body", ""), pub, now, now))
        d.commit()
        return redirect(url_for("edit", vid=cur.lastrowid, saved=1))
    return render_template("edit.html", v=row, saved=request.args.get("saved"))

@app.post("/admin/delete/<int:vid>")
@login_required
def delete(vid):
    db().execute("DELETE FROM vlogs WHERE id=?", (vid,)); db().commit()
    return redirect(url_for("admin"))

@app.post("/admin/preview")
@login_required
def preview():
    return jsonify(html=str(render_md(request.form.get("body", ""))))

# ---- Resume: viewed and downloaded from data/resume.pdf, kept in sync with a Google Drive file ----
RESUME = os.path.join(BASE, "data", "resume.pdf")
CHECKED = os.path.join(BASE, "data", "resume.checked")
MANUAL = os.path.join(BASE, "data", "resume.manual")   # present = you uploaded one, so Drive sync is paused
DRIVE_ID = os.environ.get("RESUME_DRIVE_ID", "").strip()
SYNC_EVERY = int(os.environ.get("RESUME_SYNC_MINUTES", "10")) * 60
_sync_lock = threading.Lock()

def sync_resume(force=False):
    """Fetch the shared Drive file. Only replaces resume.pdf when the content changed and is a real PDF."""
    if not DRIVE_ID or os.path.exists(MANUAL) or not _sync_lock.acquire(blocking=False):
        return
    try:
        if not force and os.path.exists(CHECKED) and time.time() - os.path.getmtime(CHECKED) < SYNC_EVERY:
            return
        os.makedirs(os.path.dirname(RESUME), exist_ok=True)
        open(CHECKED, "a").close(); os.utime(CHECKED)          # mark the attempt so failures don't hammer Drive
        for url in (f"https://drive.usercontent.google.com/download?id={DRIVE_ID}&export=download",
                    f"https://drive.google.com/uc?export=download&id={DRIVE_ID}"):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 portfolio-sync"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = r.read(15_000_000)
            except Exception:
                continue
            if data[:5] == b"%PDF-":
                if not os.path.exists(RESUME) or open(RESUME, "rb").read() != data:
                    tmp = RESUME + ".tmp"
                    open(tmp, "wb").write(data); os.replace(tmp, RESUME)
                return
    finally:
        _sync_lock.release()

def resume_ready():
    if not os.path.exists(RESUME):
        sync_resume(True)                                        # first load: wait for it
    else:
        threading.Thread(target=sync_resume, daemon=True).start()  # later loads: refresh in the background
    return os.path.exists(RESUME)

@app.get("/resume")
def resume():
    ok = resume_ready()
    updated = datetime.fromtimestamp(os.path.getmtime(RESUME)).strftime("%d %b %Y") if ok else None
    return render_template("resume.html", ok=ok, updated=updated)

@app.get("/resume/file")
def resume_file():
    if not resume_ready(): abort(404)
    return send_file(RESUME, mimetype="application/pdf", max_age=0, conditional=True)

@app.get("/resume/download")
def resume_download():
    if not resume_ready(): abort(404)
    return send_file(RESUME, mimetype="application/pdf", as_attachment=True,
                     download_name="Manas-Ranjan-Sahu-Resume.pdf", max_age=0, conditional=True)

@app.post("/admin/resume/sync")
@login_required
def resume_sync_now():
    if os.path.exists(MANUAL):
        return redirect(url_for("admin", msg="Drive sync is paused because you uploaded a resume yourself."))
    sync_resume(True)
    return redirect(url_for("admin", msg="Checked Google Drive."))

@app.post("/admin/resume/upload")
@login_required
def resume_upload():
    f = request.files.get("resume")
    data = f.read(10_000_001) if f else b""
    if not data or len(data) > 10_000_000 or data[:5] != b"%PDF-":
        return redirect(url_for("admin", msg="Please choose a PDF file under 10 MB."))
    os.makedirs(os.path.dirname(RESUME), exist_ok=True)
    tmp = RESUME + ".tmp"
    open(tmp, "wb").write(data); os.replace(tmp, RESUME)       # the previous resume is replaced
    open(MANUAL, "w").write("uploaded")
    return redirect(url_for("admin", msg="Resume updated. The previous one was replaced."))

@app.post("/admin/resume/drive")
@login_required
def resume_use_drive():
    if os.path.exists(MANUAL): os.remove(MANUAL)
    sync_resume(True)
    return redirect(url_for("admin", msg="Google Drive sync is back on."))

@app.after_request
def private_admin(r):
    if request.path.startswith(("/admin", LOGIN_PATH)):
        r.headers["X-Robots-Tag"] = "noindex, nofollow"; r.headers["Cache-Control"] = "no-store"
    return r

if __name__ == "__main__":
    app.run(debug=True)
