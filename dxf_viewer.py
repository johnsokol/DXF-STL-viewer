#!/usr/bin/env python3
"""Simple DXF viewer (tkinter canvas).

Usage:
    dxf_viewer.py [file.dxf]

Opens the given DXF file (or shows an Open dialog). Supports LINE, CIRCLE,
ARC, ELLIPSE, LWPOLYLINE, POLYLINE, POINT, TEXT, MTEXT, SOLID, 3DFACE and a
SPLINE approximation. Mouse: drag = pan, wheel = zoom, double-click = fit.
"""
import sys
import math
import tkinter as tk
from tkinter import filedialog, messagebox


# ---------------- DXF parsing ----------------
def read_pairs(text):
    lines = text.splitlines()
    pairs = []
    i = 0
    while i + 1 < len(lines):
        code = lines[i].strip()
        val = lines[i + 1]
        i += 2
        try:
            pairs.append((int(code), val.strip()))
        except ValueError:
            continue
    return pairs


KNOWN = {"LINE", "CIRCLE", "ARC", "LWPOLYLINE", "POLYLINE", "VERTEX", "SEQEND",
         "POINT", "TEXT", "MTEXT", "SOLID", "ELLIPSE", "SPLINE", "3DFACE"}


def parse_entities(pairs):
    """Return list of entities, each: {"type": str, "raw": [(code, val), ...]}."""
    has_entities = any(c == 2 and v == "ENTITIES" for c, v in pairs)
    entities = []
    in_entities = False
    k = 0
    n = len(pairs)
    while k < n:
        code, val = pairs[k]
        if code == 0:
            if val == "SECTION":
                nxt = pairs[k + 1] if k + 1 < n else None
                in_entities = bool(nxt and nxt[0] == 2 and nxt[1] == "ENTITIES")
                k += 1
                continue
            if val == "ENDSEC":
                in_entities = False
                k += 1
                continue
            consider = in_entities if has_entities else True
            if consider and val in KNOWN:
                raw = []
                j = k + 1
                while j < n and pairs[j][0] != 0:
                    raw.append(pairs[j])
                    j += 1
                entities.append({"type": val, "raw": raw})
                k = j
                continue
        k += 1
    return entities


def fval(raw, code, default=None):
    for c, v in raw:
        if c == code:
            try:
                return float(v)
            except ValueError:
                return default
    return default


def sval(raw, code, default=""):
    for c, v in raw:
        if c == code:
            return v
    return default


# ---------------- geometry build ----------------
def build_geometry(entities):
    polys = []      # (list[(x,y)], closed)
    circles = []    # (cx, cy, r)
    arcs = []       # (cx, cy, r, a0_rad, a1_rad)
    points = []     # (x, y)
    texts = []      # (x, y, h, text)

    i = 0
    n = len(entities)
    while i < n:
        e = entities[i]
        r = e["raw"]
        t = e["type"]
        if t == "LINE":
            polys.append(([(fval(r, 10, 0), fval(r, 20, 0)),
                           (fval(r, 11, 0), fval(r, 21, 0))], False))
        elif t == "CIRCLE":
            circles.append((fval(r, 10, 0), fval(r, 20, 0), fval(r, 40, 0)))
        elif t == "ARC":
            arcs.append((fval(r, 10, 0), fval(r, 20, 0), fval(r, 40, 0),
                         math.radians(fval(r, 50, 0)), math.radians(fval(r, 51, 0))))
        elif t == "ELLIPSE":
            cx, cy = fval(r, 10, 0), fval(r, 20, 0)
            mx, my = fval(r, 11, 0), fval(r, 21, 0)
            ratio = fval(r, 40, 1)
            s = fval(r, 41, 0)
            en = fval(r, 42, 2 * math.pi)
            major = math.hypot(mx, my)
            rot = math.atan2(my, mx)
            pts = []
            N = 64
            for tt in range(N + 1):
                ang = s + (en - s) * tt / N
                ex = major * math.cos(ang)
                ey = major * ratio * math.sin(ang)
                pts.append((cx + ex * math.cos(rot) - ey * math.sin(rot),
                            cy + ex * math.sin(rot) + ey * math.cos(rot)))
            polys.append((pts, abs((en - s) - 2 * math.pi) < 1e-6))
        elif t == "LWPOLYLINE":
            pts = []
            cx = cy = None
            for c, v in r:
                if c == 10:
                    if cx is not None:
                        pts.append((cx, cy))
                    cx = float(v)
                elif c == 20:
                    cy = float(v)
            if cx is not None:
                pts.append((cx, cy))
            closed = (int(fval(r, 70, 0)) & 1) == 1
            if pts:
                polys.append((pts, closed))
        elif t == "POLYLINE":
            closed = (int(fval(r, 70, 0)) & 1) == 1
            pts = []
            j = i + 1
            while j < n and entities[j]["type"] == "VERTEX":
                vr = entities[j]["raw"]
                pts.append((fval(vr, 10, 0), fval(vr, 20, 0)))
                j += 1
            if j < n and entities[j]["type"] == "SEQEND":
                j += 1
            i = j - 1
            if pts:
                polys.append((pts, closed))
        elif t in ("SOLID", "3DFACE"):
            p = []
            for cx, cy in [(10, 20), (11, 21), (12, 22), (13, 23)]:
                x, y = fval(r, cx), fval(r, cy)
                if x is not None and y is not None:
                    p.append((x, y))
            if t == "SOLID" and len(p) == 4:
                p[2], p[3] = p[3], p[2]
            if len(p) >= 3:
                polys.append((p, True))
        elif t == "POINT":
            points.append((fval(r, 10, 0), fval(r, 20, 0)))
        elif t == "TEXT":
            points  # noop
            texts.append((fval(r, 10, 0), fval(r, 20, 0), fval(r, 40, 1) or 1, sval(r, 1)))
        elif t == "MTEXT":
            txt = "".join(v for c, v in r if c in (1, 3))
            import re
            txt = re.sub(r"\\[A-Za-z][^;]*;", "", txt).replace("{", "").replace("}", "")
            texts.append((fval(r, 10, 0), fval(r, 20, 0), fval(r, 40, 1) or 1, txt))
        elif t == "SPLINE":
            pts = []
            fx = fy = None
            for c, v in r:  # fit points 11/21
                if c == 11:
                    if fx is not None:
                        pts.append((fx, fy))
                    fx = float(v)
                elif c == 21:
                    fy = float(v)
            if fx is not None:
                pts.append((fx, fy))
            if len(pts) < 2:  # fall back to control points 10/20
                pts = []
                fx = None
                for c, v in r:
                    if c == 10:
                        if fx is not None:
                            pts.append((fx, fy))
                        fx = float(v)
                    elif c == 20:
                        fy = float(v)
                if fx is not None:
                    pts.append((fx, fy))
            if len(pts) >= 2:
                polys.append((pts, False))
        i += 1

    return {"polys": polys, "circles": circles, "arcs": arcs,
            "points": points, "texts": texts}


def compute_bounds(g):
    xs, ys = [], []
    for pts, _ in g["polys"]:
        for x, y in pts:
            xs.append(x); ys.append(y)
    for cx, cy, rr in g["circles"]:
        xs += [cx - rr, cx + rr]; ys += [cy - rr, cy + rr]
    for cx, cy, rr, _, _ in g["arcs"]:
        xs += [cx - rr, cx + rr]; ys += [cy - rr, cy + rr]
    for x, y in g["points"]:
        xs.append(x); ys.append(y)
    for x, y, _, _ in g["texts"]:
        xs.append(x); ys.append(y)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


# ---------------- viewer ----------------
class Viewer(tk.Tk):
    BG = "#1e1e1e"
    FG = "#4ec9b0"

    def __init__(self, path=None):
        super().__init__()
        self.title("Simple DXF Viewer")
        self.geometry("1000x720")
        self.configure(bg="#252526")
        self._set_window_icon()

        bar = tk.Frame(self, bg="#252526")
        bar.pack(side=tk.TOP, fill=tk.X)
        tk.Button(bar, text="Open…", command=self.open_dialog).pack(side=tk.LEFT, padx=6, pady=6)
        tk.Button(bar, text="Fit", command=self.fit).pack(side=tk.LEFT, pady=6)
        self.status = tk.Label(bar, text="No file", bg="#252526", fg="#bbb", anchor="w")
        self.status.pack(side=tk.LEFT, padx=12)

        self.canvas = tk.Canvas(self, bg=self.BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.coords_lbl = tk.Label(self, text="drag=pan  wheel=zoom  dblclick=fit",
                                   bg="#252526", fg="#777", anchor="w")
        self.coords_lbl.pack(side=tk.BOTTOM, fill=tk.X)

        self.geom = None
        self.bounds = None
        self.scale = 1.0
        self.ox = 0.0
        self.oy = 0.0
        self._drag = None

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<Double-Button-1>", lambda e: self.fit())
        self.canvas.bind("<Motion>", self._on_move)
        # wheel: Linux uses Button-4/5
        self.canvas.bind("<Button-4>", lambda e: self._zoom(e, 1.15))
        self.canvas.bind("<Button-5>", lambda e: self._zoom(e, 1 / 1.15))
        self.canvas.bind("<MouseWheel>",
                         lambda e: self._zoom(e, 1.15 if e.delta > 0 else 1 / 1.15))
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Control-o>", lambda e: self.open_dialog())
        self.bind("<f>", lambda e: self.fit())
        self.bind("<q>", lambda e: self.destroy())

        if path:
            self.after(50, lambda: self.load(path))

    def _set_window_icon(self):
        """Use dxf-viewer.png (next to this script) as the window/taskbar icon."""
        import os
        png = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dxf-viewer.png")
        try:
            if os.path.exists(png):
                self._icon = tk.PhotoImage(file=png)
                self.iconphoto(True, self._icon)
        except Exception:
            pass  # icon is cosmetic; ignore failures

    # coordinate transforms (y is flipped: screen y grows downward)
    def w2s(self, x, y):
        return x * self.scale + self.ox, -y * self.scale + self.oy

    def s2w(self, sx, sy):
        return (sx - self.ox) / self.scale, (self.oy - sy) / self.scale

    def open_dialog(self):
        p = filedialog.askopenfilename(filetypes=[("DXF files", "*.dxf"), ("All", "*.*")])
        if p:
            self.load(p)

    def load(self, path):
        try:
            with open(path, "r", errors="replace") as f:
                text = f.read()
            ents = parse_entities(read_pairs(text))
            self.geom = build_geometry(ents)
            self.bounds = compute_bounds(self.geom)
        except Exception as exc:  # noqa
            messagebox.showerror("DXF Viewer", f"Could not open file:\n{exc}")
            return
        g = self.geom
        total = (len(g["polys"]) + len(g["circles"]) + len(g["arcs"])
                 + len(g["points"]) + len(g["texts"]))
        import os
        self.title(f"DXF Viewer — {os.path.basename(path)}")
        self.status.config(text=f"{os.path.basename(path)}   ({total} drawables)")
        if self.bounds:
            self.fit()
        else:
            self.status.config(text="No drawable entities found")
            self.redraw()

    def fit(self):
        if not self.bounds:
            return
        w = self.canvas.winfo_width() or 1000
        h = self.canvas.winfo_height() or 700
        pad = 30
        minx, miny, maxx, maxy = self.bounds
        bw = max(1e-9, maxx - minx)
        bh = max(1e-9, maxy - miny)
        s = min((w - 2 * pad) / bw, (h - 2 * pad) / bh)
        self.scale = s if (s and s > 0 and math.isfinite(s)) else 1.0
        cx = (minx + maxx) / 2
        cy = (miny + maxy) / 2
        self.ox = w / 2 - cx * self.scale
        self.oy = h / 2 + cy * self.scale
        self.redraw()

    def _on_press(self, e):
        self._drag = (e.x, e.y)

    def _on_drag(self, e):
        if not self._drag:
            return
        dx = e.x - self._drag[0]
        dy = e.y - self._drag[1]
        self.ox += dx
        self.oy += dy
        self._drag = (e.x, e.y)
        self.redraw()

    def _on_move(self, e):
        wx, wy = self.s2w(e.x, e.y)
        self.coords_lbl.config(text=f"x: {wx:.3f}   y: {wy:.3f}     drag=pan  wheel=zoom  dblclick=fit")

    def _zoom(self, e, factor):
        wx, wy = self.s2w(e.x, e.y)
        self.scale *= factor
        self.ox = e.x - wx * self.scale
        self.oy = e.y + wy * self.scale
        self.redraw()

    def redraw(self):
        c = self.canvas
        c.delete("all")
        if not self.geom:
            return
        g = self.geom

        # origin axes
        oxs, oys = self.w2s(0, 0)
        c.create_line(0, oys, c.winfo_width(), oys, fill="#333")
        c.create_line(oxs, 0, oxs, c.winfo_height(), fill="#333")

        for pts, closed in g["polys"]:
            if len(pts) < 2:
                if len(pts) == 1:
                    sx, sy = self.w2s(*pts[0])
                    c.create_rectangle(sx - 1, sy - 1, sx + 1, sy + 1, outline=self.FG)
                continue
            flat = []
            for x, y in pts:
                sx, sy = self.w2s(x, y)
                flat += [sx, sy]
            if closed:
                flat += flat[:2]
            c.create_line(*flat, fill=self.FG)

        for cx, cy, rr in g["circles"]:
            sx, sy = self.w2s(cx, cy)
            r = rr * self.scale
            c.create_oval(sx - r, sy - r, sx + r, sy + r, outline=self.FG)

        for cx, cy, rr, a0, a1 in g["arcs"]:
            sx, sy = self.w2s(cx, cy)
            r = rr * self.scale
            start = math.degrees(a0)
            extent = math.degrees(a1 - a0)
            # normalize extent to a positive CCW sweep
            while extent <= 0:
                extent += 360
            while extent > 360:
                extent -= 360
            c.create_arc(sx - r, sy - r, sx + r, sy + r,
                         start=start, extent=extent, style=tk.ARC, outline=self.FG)

        for x, y in g["points"]:
            sx, sy = self.w2s(x, y)
            c.create_rectangle(sx - 1.5, sy - 1.5, sx + 1.5, sy + 1.5,
                               fill="#ffd700", outline="")

        for x, y, h, txt in g["texts"]:
            if not txt:
                continue
            px = max(7, int(h * self.scale))
            if px > 4:
                sx, sy = self.w2s(x, y)
                c.create_text(sx, sy, text=txt, anchor="sw",
                              fill="#dcdcaa", font=("sans-serif", min(px, 200)))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    app = Viewer(path)
    app.mainloop()


if __name__ == "__main__":
    main()
