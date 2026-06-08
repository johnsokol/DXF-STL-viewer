# Simple DXF / STL Viewers

Lightweight viewers for 2D DXF drawings and 3D STL meshes. Python 3 + tkinter,
no external runtime dependencies (Pillow is only used to (re)generate icons).

Both are registered as the default handler for their file type, so you can
**double-click a .dxf or .stl in Files (Nautilus)** to open it.

## DXF viewer  (2D)
`dxf_viewer.py`

    python3 ~/dxfview/dxf_viewer.py path/to/file.dxf

Controls: drag = pan · scroll = zoom · double-click = fit.
Keys: Ctrl+O open · f fit · q quit.
Entities: LINE, CIRCLE, ARC, ELLIPSE, LWPOLYLINE, POLYLINE, POINT, TEXT,
MTEXT, SOLID, 3DFACE, SPLINE (approximated).

Also `dxf_viewer.html` — open in a browser and drag & drop a .dxf onto it.

## STL viewer  (3D)
`stl_viewer.py` — reads ASCII and binary STL, software-rendered flat shading
with depth sorting (painter's algorithm).

    python3 ~/dxfview/stl_viewer.py path/to/file.stl

Controls: drag = rotate · scroll = zoom · shift+drag = pan · double-click = fit.
Keys: w wireframe · f fit · o open · q quit.

"Light" viewer: meshes up to a few tens of thousands of triangles are smooth;
very large meshes get sluggish (tkinter draws one polygon per face).

## Icons / desktop integration (already installed)
Per type — `<name>` is `dxf-viewer` or `stl-viewer`:
- Icon (SVG):  ~/.local/share/icons/hicolor/scalable/apps/<name>.svg
- Icon (PNG):  ~/dxfview/<name>.png            (window/taskbar icon)
- MIME:        ~/.local/share/mime/packages/<name>.xml
- Launcher:    ~/.local/share/applications/<name>.desktop
- Defaults:    image/vnd.dxf -> dxf-viewer.desktop
               model/stl     -> stl-viewer.desktop

Regenerate the PNG icons with `make_icon.py` (DXF) and `make_stl_icon.py` (STL).
If you move this folder, update the `Exec=` path in both .desktop files.
