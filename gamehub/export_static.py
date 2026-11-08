"""Xuất 2CC thành web tĩnh để đưa lên Netlify (hoặc bất kỳ hosting tĩnh nào).

Cách dùng (trong thư mục gamehub):
    python export_static.py
Kết quả: thư mục  site/  có index.html ở gốc -> kéo thả cả thư mục này lên Netlify.
Chạy lại lệnh này mỗi khi bạn thêm/sửa/xóa game ở bản chạy trên máy.
"""
import os
import shutil
import sqlite3

from flask import render_template

import app as A

OUT = os.path.join(A.BASE, "site")


def static_url_for(endpoint, **kw):
    if endpoint == "index":
        return "/"
    if endpoint == "play":
        return "/play/%s/" % kw["gid"]
    if endpoint == "raw":
        return "/raw/%s.html" % kw["gid"]
    if endpoint == "img":
        return "/img/%s" % kw["name"]
    raise ValueError("Trang '%s' không có trong bản tĩnh" % endpoint)


def write(rel, text):
    p = os.path.join(OUT, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    A.app.jinja_env.globals["url_for"] = static_url_for
    A.app.jinja_env.globals["STATIC_EXPORT"] = True

    conn = sqlite3.connect(A.DB)
    conn.row_factory = sqlite3.Row
    games = conn.execute("SELECT * FROM games ORDER BY created_at DESC").fetchall()
    conn.close()

    ctx = A.home_context(games)

    done, skipped = 0, []
    with A.app.test_request_context("/"):
        write("index.html", render_template("index.html", **ctx))
        for g in games:
            src = os.path.join(A.GAMES, g["id"] + ".html")
            if not os.path.exists(src):
                skipped.append(g["title"])
                continue
            write("play/%s/index.html" % g["id"], render_template("play.html", game=g))
            os.makedirs(os.path.join(OUT, "raw"), exist_ok=True)
            shutil.copyfile(src, os.path.join(OUT, "raw", g["id"] + ".html"))
            for key in ("image", "logo"):
                if g[key]:
                    s = os.path.join(A.IMGS, g[key])
                    if os.path.exists(s):
                        os.makedirs(os.path.join(OUT, "img"), exist_ok=True)
                        shutil.copyfile(s, os.path.join(OUT, "img", g[key]))
            done += 1

        # logo website (nếu có)
        logo = A.site_info()["logo"]
        if logo and os.path.exists(os.path.join(A.IMGS, logo)):
            os.makedirs(os.path.join(OUT, "img"), exist_ok=True)
            shutil.copyfile(os.path.join(A.IMGS, logo), os.path.join(OUT, "img", logo))

    # Game chạy trong sandbox, tách khỏi trang chính
    write("_headers",
          "/raw/*\n  Content-Security-Policy: sandbox allow-scripts allow-pointer-lock "
          "allow-popups allow-forms allow-modals\n  Content-Type: text/html; charset=utf-8\n"
          "  Cache-Control: no-cache\n")

    print("Đã xuất %d game vào thư mục: %s" % (done, OUT))
    if skipped:
        print("Bỏ qua (thiếu file game): " + ", ".join(skipped))
    print("Tiếp theo: kéo thả thư mục 'site' lên Netlify (index.html nằm ở gốc).")


if __name__ == "__main__":
    main()
