import io
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
import zipfile
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   send_file, send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
GAMES = os.path.join(DATA, "games")
IMGS = os.path.join(DATA, "images")
BACKUPS = os.path.join(DATA, "backups")
DB = os.path.join(DATA, "gamehub.db")
for d in (GAMES, IMGS, BACKUPS):
    os.makedirs(d, exist_ok=True)

ID_RE = re.compile(r"^[0-9a-f]{8}$")
IMG_RE = re.compile(r"^[0-9a-f]{16}\.(png|jpg|jpeg|gif|webp)$")
BK_RE = re.compile(r"^[A-Za-z0-9_\-]+\.zip$")
IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp")
KEEP_BACKUPS = 20

# Danh sách thể loại (sửa tùy ý). Mỗi game chọn tối đa MAX_GENRES thể loại.
GENRES = ["Hành động", "Phiêu lưu", "Giải đố", "Chiến thuật", "Arcade", "Bắn súng",
          "Đua xe", "Thể thao", "Nhập vai", "Mô phỏng", "Cờ bàn", "Trí nhớ",
          "Âm nhạc", "Trẻ em"]
MAX_GENRES = 3
ORIENTS = ("any", "landscape", "portrait")  # tự do / chỉ ngang / chỉ dọc
TOP_MAX = 5  # tối đa 5 game trong mục "Top game được yêu thích"
PLAY_COOLDOWN = 1800  # 1 người chơi lại cùng game trong 30 phút chỉ tính 1 lượt

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

_key = os.path.join(DATA, "secret.key")
if not os.path.exists(_key):
    with open(_key, "w") as f:
        f.write(secrets.token_hex(32))
with open(_key) as f:
    app.secret_key = f.read().strip()


# ---------- database ----------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()


def init_db():
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS games(
        id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT DEFAULT '',
        image TEXT DEFAULT '', plays INTEGER DEFAULT 0, created_at TEXT)""")
    c.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
    # nâng cấp DB cũ: thêm cột logo + thể loại, bảng thống kê theo ngày
    cols = {r[1] for r in c.execute("PRAGMA table_info(games)")}
    if "logo" not in cols:
        c.execute("ALTER TABLE games ADD COLUMN logo TEXT DEFAULT ''")
    if "genres" not in cols:
        c.execute("ALTER TABLE games ADD COLUMN genres TEXT DEFAULT ''")
    if "orientation" not in cols:
        c.execute("ALTER TABLE games ADD COLUMN orientation TEXT DEFAULT 'any'")
    if "hot" not in cols:
        c.execute("ALTER TABLE games ADD COLUMN hot INTEGER DEFAULT 0")
    if "top_rank" not in cols:
        c.execute("ALTER TABLE games ADD COLUMN top_rank INTEGER DEFAULT 0")
    c.execute("""CREATE TABLE IF NOT EXISTS plays_daily(
        game_id TEXT, day TEXT, n INTEGER DEFAULT 0, PRIMARY KEY(game_id, day))""")
    if not c.execute("SELECT 1 FROM settings WHERE key='admin_hash'").fetchone():
        c.execute("INSERT INTO settings VALUES('admin_user','admin')")
        pw = os.environ.get("ADMIN_PASSWORD", "Admin@123")
        c.execute("INSERT INTO settings VALUES('admin_hash',?)", (generate_password_hash(pw),))
    c.commit()
    c.close()


init_db()


def get_setting(k):
    r = db().execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone()
    return r["value"] if r else None


app.jinja_env.filters["glist"] = lambda s: [x for x in (s or "").split(",") if x]


# ---------- security helpers ----------
def csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


app.jinja_env.globals["csrf"] = csrf
app.jinja_env.globals["GENRES"] = GENRES
app.jinja_env.globals["MAX_GENRES"] = MAX_GENRES
app.jinja_env.globals["TOP_MAX"] = TOP_MAX


@app.before_request
def check_csrf():
    if request.method == "POST":
        sent = request.form.get("csrf", "").encode()
        real = session.get("csrf", "x").encode()
        if not secrets.compare_digest(sent, real):
            abort(400)


def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return f(*a, **k)
    return w


@app.context_processor
def inject():
    return {"is_admin": bool(session.get("admin"))}


# ---------- image helpers ----------
def bad_image(f):
    """True nếu có file nhưng sai định dạng ảnh."""
    return bool(f and f.filename and os.path.splitext(f.filename)[1].lower() not in IMG_EXT)


def store_image(f, old=""):
    """Lưu ảnh mới (nếu có), xóa ảnh cũ, trả về tên file hiện tại."""
    if not f or not f.filename:
        return old
    name = uuid.uuid4().hex[:16] + os.path.splitext(f.filename)[1].lower()
    f.save(os.path.join(IMGS, name))
    if old:
        p = os.path.join(IMGS, old)
        if os.path.exists(p):
            os.remove(p)
    return name


def clean_genres(values):
    out = []
    for x in values:
        if x in GENRES and x not in out:
            out.append(x)
    return out


# ---------- backup ----------
def build_zip():
    rows = [dict(r) for r in db().execute("SELECT * FROM games ORDER BY created_at")]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("games.json", json.dumps(rows, ensure_ascii=False, indent=2))
        for r in rows:
            p = os.path.join(GAMES, r["id"] + ".html")
            if os.path.exists(p):
                z.write(p, "games/" + r["id"] + ".html")
            for key in ("image", "logo"):
                if r.get(key):
                    p = os.path.join(IMGS, r[key])
                    if os.path.exists(p):
                        z.write(p, "images/" + r[key])
    buf.seek(0)
    return buf


def auto_backup(prefix="auto"):
    name = datetime.now().strftime(prefix + "-%Y%m%d-%H%M%S.zip")
    with open(os.path.join(BACKUPS, name), "wb") as f:
        f.write(build_zip().getvalue())
    files = sorted((os.path.join(BACKUPS, x) for x in os.listdir(BACKUPS) if x.endswith(".zip")),
                   key=os.path.getmtime)
    for old in files[:-KEEP_BACKUPS]:
        os.remove(old)


def list_backups():
    out = []
    for x in os.listdir(BACKUPS):
        if x.endswith(".zip"):
            p = os.path.join(BACKUPS, x)
            out.append((x, os.path.getmtime(p), os.path.getsize(p)))
    out.sort(key=lambda t: -t[1])
    return [(n, datetime.fromtimestamp(m).strftime("%d/%m/%Y %H:%M"), round(s / 1024, 1))
            for n, m, s in out]


# ---------- public pages ----------
def home_context(games):
    """Dữ liệu cho trang chủ (dùng chung cho bản chạy Flask và bản xuất tĩnh)."""
    counts = {}
    for g_ in games:
        for x in (g_["genres"] or "").split(","):
            if x:
                counts[x] = counts.get(x, 0) + 1
    top = sorted((g_ for g_ in games if g_["top_rank"]), key=lambda g_: g_["top_rank"])[:TOP_MAX]
    return {"games": games,
            "genre_counts": [(x, counts[x]) for x in GENRES if x in counts],
            "top_games": top,
            "hot_count": sum(1 for g_ in games if g_["hot"])}


@app.route("/")
def index():
    games = db().execute("SELECT * FROM games ORDER BY created_at DESC").fetchall()
    return render_template("index.html", **home_context(games))


@app.route("/play/<gid>")
def play(gid):
    if not ID_RE.match(gid):
        abort(404)
    if not db().execute("SELECT 1 FROM games WHERE id=?", (gid,)).fetchone():
        abort(404)
    now = time.time()
    seen = {k: v for k, v in session.get("seen", {}).items() if now - v < PLAY_COOLDOWN}
    if gid not in seen:
        db().execute("UPDATE games SET plays=plays+1 WHERE id=?", (gid,))
        db().execute("""INSERT INTO plays_daily(game_id,day,n) VALUES(?,?,1)
                        ON CONFLICT(game_id,day) DO UPDATE SET n=n+1""",
                     (gid, datetime.now().strftime("%Y-%m-%d")))
        db().commit()
        seen[gid] = now
    session["seen"] = seen
    g_ = db().execute("SELECT * FROM games WHERE id=?", (gid,)).fetchone()
    return render_template("play.html", game=g_)


@app.route("/raw/<gid>")
def raw(gid):
    if not ID_RE.match(gid):
        abort(404)
    p = os.path.join(GAMES, gid + ".html")
    if not os.path.exists(p):
        abort(404)
    resp = send_file(p, mimetype="text/html")
    # Game chạy trong sandbox: không đụng được vào phiên đăng nhập của trang web
    resp.headers["Content-Security-Policy"] = (
        "sandbox allow-scripts allow-pointer-lock allow-popups allow-forms allow-modals")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/img/<name>")
def img(name):
    if not IMG_RE.match(name):
        abort(404)
    return send_from_directory(IMGS, name)


# ---------- auth ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "")
        if u == get_setting("admin_user") and check_password_hash(get_setting("admin_hash"), p):
            session.clear()
            session["admin"] = True
            return redirect(url_for("admin"))
        flash("Sai tên đăng nhập hoặc mật khẩu.", "err")
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------- admin ----------
@app.route("/admin")
@admin_required
def admin():
    games = db().execute("SELECT * FROM games ORDER BY created_at DESC").fetchall()
    edit = None
    eid = request.args.get("edit", "")
    if ID_RE.match(eid):
        edit = db().execute("SELECT * FROM games WHERE id=?", (eid,)).fetchone()

    # thống kê lượt chơi
    today = datetime.now().date()
    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    m = {r["day"]: r["n"] for r in db().execute(
        "SELECT day, SUM(n) n FROM plays_daily WHERE day>=? GROUP BY day", (days[0].isoformat(),))}
    chart = [(d.strftime("%d/%m"), m.get(d.isoformat(), 0)) for d in days]
    per = {}
    for r in db().execute(
            """SELECT game_id, SUM(CASE WHEN day=? THEN n ELSE 0 END) t,
                      SUM(CASE WHEN day>=? THEN n ELSE 0 END) w
               FROM plays_daily GROUP BY game_id""",
            (today.isoformat(), (today - timedelta(days=6)).isoformat())):
        per[r["game_id"]] = (r["t"], r["w"])
    stats = {
        "total": sum(x["plays"] for x in games),
        "today": sum(v[0] for v in per.values()),
        "week": sum(v[1] for v in per.values()),
        "chart": chart,
        "cmax": max([n for _, n in chart] + [1]),
        "per": per,
    }
    return render_template("admin.html", games=games, edit=edit, backups=list_backups(),
                           username=get_setting("admin_user"), stats=stats)


@app.post("/admin/save")
@admin_required
def save():
    gid = request.form.get("id", "").strip()
    back = url_for("admin", edit=gid) if gid else url_for("admin")
    title = request.form.get("title", "").strip()[:100]
    desc = request.form.get("description", "").strip()[:500]
    if not title:
        flash("Vui lòng nhập tên game.", "err")
        return redirect(back)

    raw_genres = [x for x in request.form.getlist("genres") if x in GENRES]
    genres = clean_genres(raw_genres)
    if len(genres) > MAX_GENRES:
        flash("Mỗi game chỉ được chọn tối đa %d thể loại." % MAX_GENRES, "err")
        return redirect(back)

    code = None
    f = request.files.get("html_file")
    if f and f.filename:
        code = f.read()
    elif request.form.get("html_code", "").strip():
        code = request.form["html_code"].encode("utf-8")

    row = None
    if gid:
        if not ID_RE.match(gid):
            abort(400)
        row = db().execute("SELECT * FROM games WHERE id=?", (gid,)).fetchone()
        if not row:
            abort(404)
    elif code is None:
        flash("Cần tải lên file HTML hoặc dán code HTML.", "err")
        return redirect(back)

    im_f, logo_f = request.files.get("image"), request.files.get("logo")
    if bad_image(im_f) or bad_image(logo_f):
        flash("Ảnh phải là png, jpg, gif hoặc webp.", "err")
        return redirect(back)
    image = store_image(im_f, row["image"] if row else "")
    logo = store_image(logo_f, row["logo"] if row else "")
    gs = ",".join(genres)
    ori = request.form.get("orientation", "any")
    if ori not in ORIENTS:
        ori = "any"
    hot = 1 if request.form.get("hot") else 0
    try:
        top_rank = int(request.form.get("top_rank", "") or 0)
    except ValueError:
        top_rank = 0
    if not 1 <= top_rank <= TOP_MAX:
        top_rank = 0

    if row:
        db().execute("""UPDATE games SET title=?, description=?, image=?, logo=?, genres=?, orientation=?,
                        hot=?, top_rank=? WHERE id=?""",
                     (title, desc, image, logo, gs, ori, hot, top_rank, gid))
    else:
        gid = uuid.uuid4().hex[:8]
        db().execute("""INSERT INTO games(id,title,description,image,logo,genres,orientation,hot,top_rank,plays,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?,0,?)""",
                     (gid, title, desc, image, logo, gs, ori, hot, top_rank,
                      datetime.now().isoformat(timespec="seconds")))
    if code is not None:
        with open(os.path.join(GAMES, gid + ".html"), "wb") as out:
            out.write(code)
    db().commit()
    auto_backup()
    flash("Đã lưu game: " + title, "ok")
    return redirect(url_for("admin"))


@app.post("/admin/delete/<gid>")
@admin_required
def delete(gid):
    if not ID_RE.match(gid):
        abort(400)
    row = db().execute("SELECT * FROM games WHERE id=?", (gid,)).fetchone()
    if row:
        auto_backup("before-delete")  # luôn sao lưu trước khi xóa
        paths = [os.path.join(GAMES, gid + ".html")]
        paths += [os.path.join(IMGS, row[k]) for k in ("image", "logo") if row[k]]
        for p in paths:
            if os.path.exists(p):
                os.remove(p)
        db().execute("DELETE FROM games WHERE id=?", (gid,))
        db().execute("DELETE FROM plays_daily WHERE game_id=?", (gid,))
        db().commit()
        flash("Đã xóa game (có bản sao lưu trước khi xóa).", "ok")
    return redirect(url_for("admin"))


@app.post("/admin/backup/now")
@admin_required
def backup_now():
    auto_backup("manual")
    flash("Đã tạo bản sao lưu.", "ok")
    return redirect(url_for("admin"))


@app.route("/admin/backup/download")
@admin_required
def backup_download():
    name = datetime.now().strftime("gamehub-backup-%Y%m%d-%H%M%S.zip")
    return send_file(build_zip(), mimetype="application/zip", as_attachment=True, download_name=name)


@app.route("/admin/backup/file/<name>")
@admin_required
def backup_file(name):
    if not BK_RE.match(name):
        abort(404)
    return send_from_directory(BACKUPS, name, as_attachment=True)


@app.post("/admin/backup/restore")
@admin_required
def backup_restore():
    f = request.files.get("zipfile")
    if not f or not f.filename:
        flash("Chưa chọn file sao lưu.", "err")
        return redirect(url_for("admin"))
    try:
        z = zipfile.ZipFile(io.BytesIO(f.read()))
        rows = json.loads(z.read("games.json").decode("utf-8"))
    except Exception:
        flash("File sao lưu không hợp lệ.", "err")
        return redirect(url_for("admin"))
    auto_backup("before-restore")
    names = set(z.namelist())

    def restore_img(name):
        name = str(name or "")
        if not name or not IMG_RE.match(name) or "images/" + name not in names:
            return ""
        with open(os.path.join(IMGS, name), "wb") as out:
            out.write(z.read("images/" + name))
        return name

    n = 0
    for r in rows:
        gid = str(r.get("id", ""))
        if not ID_RE.match(gid) or "games/" + gid + ".html" not in names:
            continue
        with open(os.path.join(GAMES, gid + ".html"), "wb") as out:
            out.write(z.read("games/" + gid + ".html"))
        image, logo = restore_img(r.get("image")), restore_img(r.get("logo"))
        genres = ",".join(clean_genres(str(r.get("genres", "") or "").split(","))[:MAX_GENRES])
        ori = r.get("orientation") if r.get("orientation") in ORIENTS else "any"
        hot = 1 if r.get("hot") else 0
        try:
            top_rank = int(r.get("top_rank", 0) or 0)
        except (TypeError, ValueError):
            top_rank = 0
        if not 1 <= top_rank <= TOP_MAX:
            top_rank = 0
        db().execute("""INSERT INTO games(id,title,description,image,logo,genres,orientation,hot,top_rank,plays,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                        title=excluded.title, description=excluded.description,
                        image=excluded.image, logo=excluded.logo, genres=excluded.genres,
                        orientation=excluded.orientation, hot=excluded.hot,
                        top_rank=excluded.top_rank, plays=excluded.plays""",
                     (gid, str(r.get("title", "Game"))[:100], str(r.get("description", ""))[:500],
                      image, logo, genres, ori, hot, top_rank, int(r.get("plays", 0) or 0),
                      r.get("created_at") or datetime.now().isoformat(timespec="seconds")))
        n += 1
    db().commit()
    flash("Đã khôi phục %d game." % n, "ok")
    return redirect(url_for("admin"))


@app.post("/admin/password")
@admin_required
def change_password():
    cur = request.form.get("current", "")
    new_user = request.form.get("username", "").strip()
    new = request.form.get("new", "")
    if not check_password_hash(get_setting("admin_hash"), cur):
        flash("Mật khẩu hiện tại không đúng.", "err")
    elif len(new) < 6 or not new_user:
        flash("Tên đăng nhập không được trống, mật khẩu mới tối thiểu 6 ký tự.", "err")
    else:
        db().execute("UPDATE settings SET value=? WHERE key='admin_user'", (new_user,))
        db().execute("UPDATE settings SET value=? WHERE key='admin_hash'", (generate_password_hash(new),))
        db().commit()
        flash("Đã đổi tài khoản admin.", "ok")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
