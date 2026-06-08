#!/usr/bin/env python3
"""Simple STL viewer (tkinter, software-rendered).

Usage:
    stl_viewer.py [file.stl]

Loads ASCII or binary STL and shows a flat-shaded, depth-sorted view.
Mouse: drag = rotate, wheel = zoom, shift+drag = pan, double-click = fit.
Keys: w = toggle wireframe, f = fit, o = open, q = quit.

Intended for "light" viewing — meshes up to a few tens of thousands of
triangles render fine; very large meshes will be sluggish (tkinter draws
one polygon per face).
"""
import sys
import os
import math
import struct
import tkinter as tk
from tkinter import filedialog, messagebox


# ---------------- STL parsing ----------------
def load_stl(path):
    """Return a flat list of triangles: [((x,y,z),(x,y,z),(x,y,z)), ...]."""
    with open(path, "rb") as f:
        data = f.read()
    # ASCII STL starts with "solid" AND contains "facet"; binary may also start
    # with "solid", so confirm by checking for "facet" in the head.
    head = data[:512].lstrip()
    is_ascii = head[:5].lower() == b"solid" and b"facet" in data[:2048].lower()
    if is_ascii:
        try:
            return _parse_ascii(data.decode("utf-8", "replace"))
        except Exception:
            return _parse_binary(data)  # fall back if it was mislabeled
    return _parse_binary(data)


def _parse_ascii(text):
    tris = []
    verts = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("vertex"):
            parts = s.split()
            verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
            if len(verts) == 3:
                tris.append((verts[0], verts[1], verts[2]))
                verts = []
        elif s.startswith("endloop"):
            verts = []
    return tris


def _parse_binary(data):
    if len(data) < 84:
        return []
    (count,) = struct.unpack_from("<I", data, 80)
    tris = []
    off = 84
    rec = struct.Struct("<12fH")
    for _ in range(count):
        if off + 50 > len(data):
            break
        vals = rec.unpack_from(data, off)
        off += 50
        # vals[0:3] = normal (ignored), 3:6 v1, 6:9 v2, 9:12 v3
        tris.append(((vals[3], vals[4], vals[5]),
                     (vals[6], vals[7], vals[8]),
                     (vals[9], vals[10], vals[11])))
    return tris


def model_bounds(tris):
    if not tris:
        return None
    xs = [v[0] for t in tris for v in t]
    ys = [v[1] for t in tris for v in t]
    zs = [v[2] for t in tris for v in t]
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


# ---------------- viewer ----------------
class Viewer(tk.Tk):
    BG = "#1e1e1e"
    BASE = (0x4e, 0xc9, 0xb0)   # mint, matches the DXF viewer accent
    EDGE = "#2a2a2a"

    def __init__(self, path=None):
        super().__init__()
        self.title("Simple STL Viewer")
        self.geometry("1000x720")
        self.configure(bg="#252526")
        self._set_window_icon()

        bar = tk.Frame(self, bg="#252526")
        bar.pack(side=tk.TOP, fill=tk.X)
        tk.Button(bar, text="Open…", command=self.open_dialog).pack(side=tk.LEFT, padx=6, pady=6)
        tk.Button(bar, text="Fit", command=self.fit).pack(side=tk.LEFT, pady=6)
        self.wire = tk.BooleanVar(value=False)
        tk.Checkbutton(bar, text="Wireframe", variable=self.wire, command=self.redraw,
                       bg="#252526", fg="#bbb", selectcolor="#252526",
                       activebackground="#252526", activeforeground="#fff").pack(side=tk.LEFT, padx=6)
        self.status = tk.Label(bar, text="No file", bg="#252526", fg="#bbb", anchor="w")
        self.status.pack(side=tk.LEFT, padx=12)

        self.canvas = tk.Canvas(self, bg=self.BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.hint = tk.Label(self, text="drag=rotate  wheel=zoom  shift+drag=pan  dblclick=fit  w=wireframe",
                             bg="#252526", fg="#777", anchor="w")
        self.hint.pack(side=tk.BOTTOM, fill=tk.X)

        self.tris = []
        self.center = (0, 0, 0)
        self.rx, self.ry = -1.1, 0.5     # initial tilt so we see it in 3D
        self.scale = 1.0
        self.px, self.py = 0.0, 0.0      # pan offset (screen px)
        self._drag = None
        self._pan = None

        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._rotate)
        self.canvas.bind("<Shift-ButtonPress-1>", self._press_pan)
        self.canvas.bind("<Shift-B1-Motion>", self._do_pan)
        self.canvas.bind("<Double-Button-1>", lambda e: self.fit())
        self.canvas.bind("<Button-4>", lambda e: self._zoom(1.15))
        self.canvas.bind("<Button-5>", lambda e: self._zoom(1 / 1.15))
        self.canvas.bind("<MouseWheel>", lambda e: self._zoom(1.15 if e.delta > 0 else 1 / 1.15))
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.bind("<w>", lambda e: (self.wire.set(not self.wire.get()), self.redraw()))
        self.bind("<f>", lambda e: self.fit())
        self.bind("<o>", lambda e: self.open_dialog())
        self.bind("<Control-o>", lambda e: self.open_dialog())
        self.bind("<q>", lambda e: self.destroy())

        if path:
            self.after(50, lambda: self.load(path))

    def _set_window_icon(self):
        png = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stl-viewer.png")
        try:
            if os.path.exists(png):
                self._icon = tk.PhotoImage(file=png)
                self.iconphoto(True, self._icon)
        except Exception:
            pass

    def open_dialog(self):
        p = filedialog.askopenfilename(filetypes=[("STL files", "*.stl"), ("All", "*.*")])
        if p:
            self.load(p)

    def load(self, path):
        try:
            self.tris = load_stl(path)
        except Exception as exc:  # noqa
            messagebox.showerror("STL Viewer", f"Could not open file:\n{exc}")
            return
        b = model_bounds(self.tris)
        self.title(f"STL Viewer — {os.path.basename(path)}")
        if not b:
            self.status.config(text="No triangles found")
            self.redraw()
            return
        self.center = ((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2)
        self._extent = max(b[3] - b[0], b[4] - b[1], b[5] - b[2]) or 1.0
        dims = f"{b[3]-b[0]:.2f} × {b[4]-b[1]:.2f} × {b[5]-b[2]:.2f}"
        self.status.config(text=f"{os.path.basename(path)}   ({len(self.tris)} triangles · {dims})")
        self.rx, self.ry = -1.1, 0.5
        self.px = self.py = 0.0
        self.fit()

    def fit(self):
        if not self.tris:
            return
        w = self.canvas.winfo_width() or 1000
        h = self.canvas.winfo_height() or 700
        self.scale = 0.45 * min(w, h) / (self._extent / 2)
        self.px = self.py = 0.0
        self.redraw()

    # ---- interaction ----
    def _press(self, e):
        self._drag = (e.x, e.y)

    def _rotate(self, e):
        if not self._drag:
            return
        dx = e.x - self._drag[0]
        dy = e.y - self._drag[1]
        self.ry += dx * 0.01
        self.rx += dy * 0.01
        self._drag = (e.x, e.y)
        self.redraw()

    def _press_pan(self, e):
        self._pan = (e.x, e.y)

    def _do_pan(self, e):
        if not self._pan:
            return
        self.px += e.x - self._pan[0]
        self.py += e.y - self._pan[1]
        self._pan = (e.x, e.y)
        self.redraw()

    def _zoom(self, f):
        self.scale *= f
        self.redraw()

    # ---- rendering ----
    def redraw(self):
        c = self.canvas
        c.delete("all")
        if not self.tris:
            return
        w = c.winfo_width() or 1000
        h = c.winfo_height() or 700
        cx0, cy0, cz0 = self.center
        s = self.scale
        ox = w / 2 + self.px
        oy = h / 2 + self.py

        # rotation matrix (X then Y)
        cosx, sinx = math.cos(self.rx), math.sin(self.rx)
        cosy, siny = math.cos(self.ry), math.sin(self.ry)
        light = (0.3, 0.4, 0.85)   # view-space light direction (normalized below)
        ln = math.sqrt(sum(v * v for v in light))
        light = tuple(v / ln for v in light)
        base = self.BASE
        wire = self.wire.get()

        faces = []  # (avg_depth, screen_pts, fill)
        for tri in self.tris:
            rp = []
            for (x, y, z) in tri:
                # translate to center
                x -= cx0; y -= cy0; z -= cz0
                # rotate about X
                y2 = y * cosx - z * sinx
                z2 = y * sinx + z * cosx
                # rotate about Y
                x3 = x * cosy + z2 * siny
                z3 = -x * siny + z2 * cosy
                rp.append((x3, y2, z3))
            # face normal in view space
            ax, ay, az = rp[1][0] - rp[0][0], rp[1][1] - rp[0][1], rp[1][2] - rp[0][2]
            bx, by, bz = rp[2][0] - rp[0][0], rp[2][1] - rp[0][1], rp[2][2] - rp[0][2]
            nx = ay * bz - az * by
            ny = az * bx - ax * bz
            nz = ax * by - ay * bx
            nlen = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            nx, ny, nz = nx / nlen, ny / nlen, nz / nlen
            # shading: ambient + diffuse (use abs so back faces aren't black)
            diff = abs(nx * light[0] + ny * light[1] + nz * light[2])
            shade = 0.25 + 0.75 * diff
            fill = "#%02x%02x%02x" % (
                min(255, int(base[0] * shade)),
                min(255, int(base[1] * shade)),
                min(255, int(base[2] * shade)),
            )
            # orthographic projection (screen y down)
            pts = []
            depth = 0.0
            for (x3, y2, z3) in rp:
                pts.append((ox + x3 * s, oy - y2 * s))
                depth += z3
            faces.append((depth / 3.0, pts, fill))

        # painter's algorithm: far (small z, away from viewer) first
        faces.sort(key=lambda fz: fz[0])
        if wire:
            for _, pts, _ in faces:
                flat = [v for p in pts for v in p]
                c.create_polygon(*flat, outline=self.EDGE, fill="", width=1)
            # overlay edges in accent for visibility
            for _, pts, _ in faces:
                flat = [v for p in pts for v in p]
                c.create_polygon(*flat, outline="#4ec9b0", fill="")
        else:
            for _, pts, fill in faces:
                flat = [v for p in pts for v in p]
                c.create_polygon(*flat, fill=fill, outline=fill)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    Viewer(path).mainloop()


if __name__ == "__main__":
    main()
