"""The radial drop menu that pops up under the cursor while you Shift+drag a file.

Rendering: the moment the menu opens we snapshot the screen behind it; a worker thread then
refracts that snapshot through the menu's shape (see liquid.py). Until that's ready (~60 ms)
a cheap frosted version is drawn, so the menu still appears instantly."""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import (QEasingCurve, QObject, QPoint, QPointF, QRectF, QRunnable, Qt,
                            QThreadPool, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import (QColor, QCursor, QFont, QGuiApplication, QImage, QPainter,
                           QPainterPath, QPen, QPixmap, QRadialGradient)
from PySide6.QtWidgets import QWidget

from . import glass
from .util import resolve_shortcuts, ui_family


@dataclass
class Item:
    label: str
    glyph: str = ""
    run: Callable[[list[str]], None] | None = None
    key: str = ""
    hint: str = ""


SIZE = 400          # window size (room for shadow + hover pop)
R_OUT = 158         # outer radius of petals
R_IN = 60           # inner radius of petals
R_HUB = 50          # hub radius
GAP_DEG = 3.2
CORNER = 10


def sector_path(c: QPointF, r0: float, r1: float, a0: float, a1: float) -> QPainterPath:
    """Annular sector between angles a0..a1 (degrees, Qt convention: 0 = 3 o'clock, CCW)."""
    path = QPainterPath()
    outer = QRectF(c.x() - r1, c.y() - r1, 2 * r1, 2 * r1)
    inner = QRectF(c.x() - r0, c.y() - r0, 2 * r0, 2 * r0)
    path.arcMoveTo(outer, a0)
    path.arcTo(outer, a0, a1 - a0)
    path.arcTo(inner, a1, -(a1 - a0))
    path.closeSubpath()
    return path


def angles(n: int, i: int) -> tuple[float, float]:
    span = 360.0 / n
    start = 90 + span / 2 - (i + 1) * span   # first petal centred at 12 o'clock, clockwise
    return start + GAP_DEG / 2, start + span - GAP_DEG / 2


# ---------------------------------------------------------------- background render
class _RenderSig(QObject):
    done = Signal(int, int, QImage, bool)   # serial, petal count, image, is_light


class _RenderJob(QRunnable):
    def __init__(self, serial: int, n: int, backdrop):
        super().__init__()
        self.serial, self.n, self.backdrop = serial, n, backdrop
        self.sig = _RenderSig()

    def run(self):
        try:
            from . import liquid
            c = SIZE / 2
            fields = [liquid.sdf_circle(SIZE, SIZE, c, c, R_HUB)]
            for i in range(self.n):
                a0, a1 = angles(self.n, i)
                fields.append(liquid.sdf_ring_sector(SIZE, SIZE, c, c, R_IN, R_OUT, a0, a1, CORNER))
            sdf = liquid.union(*fields)
            img, light = liquid.render(self.backdrop, sdf, liquid.GlassStyle())
            sh = liquid.shadow(sdf, spread=26, opacity=0.42 if light else 0.30, offset=(0, 8))
            sh.alpha_composite(img)
            try:
                self.sig.done.emit(self.serial, self.n, glass.qimage_from_pil(sh), light)
            except RuntimeError:
                pass
        except Exception:  # pragma: no cover - fall back to the painted glass
            import traceback
            traceback.print_exc()


class RadialMenu(QWidget):
    activated = Signal(object, list)     # Item, paths
    dismissed = Signal()

    def __init__(self, build_rings: Callable[[list[str]], dict[str, list[Item]]],
                 describe: Callable[[list[str]], str]):
        super().__init__(None)
        self.build_rings = build_rings
        self.describe = describe
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint |
                            Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.resize(SIZE, SIZE)

        self.paths: list[str] = []
        self.rings: dict[str, list[Item]] = {}
        self.ring_names: list[str] = []
        self.ring_idx = 0
        self.requested_ring: str | None = None
        self.hover = -1          # petal index, -2 = hub, -1 = none
        self.cursor_pos = QPointF(SIZE / 2, SIZE / 2)
        self.hub_text = ""
        self.backdrop: QPixmap | None = None     # blurred, for the instant fallback
        self._raw_backdrop = None                 # PIL image for the liquid renderer
        self.liquid: dict[int, QImage] = {}       # petal count -> rendered glass
        self.is_light = False
        self._serial = 0
        self.got_drag = False
        self.hub_armed = False
        self.click_mode = False  # opened from tray/menu instead of a drag
        self._t = 1.0            # pop-in animation 0..1
        self._swap = 1.0         # ring-swap animation 0..1
        self.spring: list[float] = []   # per-petal hover amount 0..1 (eased every frame)
        self.hub_spring = 0.0

        self.anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=190,
                                      easingCurve=QEasingCurve.OutBack)
        self.anim.valueChanged.connect(self._set_t)
        self.swap_anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=220,
                                           easingCurve=QEasingCurve.OutCubic)
        self.swap_anim.valueChanged.connect(self._set_swap)
        self.hub_timer = QTimer(self, singleShot=True, interval=900, timeout=self._hub_timeout)
        self.frame = QTimer(self, interval=16, timeout=self._tick)   # 60 fps springs

    def _hub_timeout(self):
        self.next_ring()
        if self.hover == -2 and len(self.ring_names) > 1:
            self.hub_timer.setInterval(1200)
            self.hub_timer.start()

    # ------------------------------------------------------------ show / hide
    def popup(self, pos: QPoint | None = None, paths: list[str] | None = None, ring: str | None = None):
        self.requested_ring = ring
        pos = pos or QCursor.pos()
        tl = pos - QPoint(SIZE // 2, SIZE // 2)
        scr = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        g = scr.geometry()
        tl.setX(min(max(tl.x(), g.left()), g.right() - SIZE))
        tl.setY(min(max(tl.y(), g.top()), g.bottom() - SIZE))
        # snapshot what's underneath *before* we appear
        self._serial += 1
        self.liquid = {}
        try:
            if sys.platform == "darwin":
                # macOS captures "below the drag window": the drag picture never gets in
                raw = glass.grab_screen(tl.x(), tl.y(), SIZE, SIZE)
                if raw is None:
                    raise RuntimeError("capture failed")
                from . import platform_mac
                print("menu: mac windows at cursor:", "; ".join(platform_mac.LAST_SWEEP), flush=True)
                if self.got_drag or paths is None:
                    # belt and braces: Finder's drag picture (icon + name label) sits on the
                    # cursor; erase that area — it ends up under the hub, blurred anyway
                    cx, cy = pos.x() - tl.x(), pos.y() - tl.y()
                    raw = glass.inpaint_rects(raw, [(cx - 70, cy - 64, cx + 70, cy + 64)])
                shot = QPixmap.fromImage(glass.qimage_from_pil(raw))
            else:
                with glass.hidden_drag_images() as hid:
                    shot = scr.grabWindow(0, tl.x() - g.left(), tl.y() - g.top(), SIZE, SIZE)
                if hid.hwnds:
                    print(f"menu: hid {len(hid.hwnds)} drag image(s) during capture: {'; '.join(hid.info)}", flush=True)
                elif hid.info:
                    print(f"menu: drag-image sweep: {'; '.join(hid.info)}", flush=True)
                raw = glass.pil_from_qimage(
                    shot.toImage().scaled(SIZE, SIZE, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
                if sys.platform.startswith("linux") and paths is None:
                    # X11 drag icons (Thunar/GTK) sit on the cursor: erase that patch
                    cx, cy = pos.x() - tl.x(), pos.y() - tl.y()
                    hid.rects = [(pos.x() - 60, pos.y() - 60, pos.x() + 60, pos.y() + 60)]
                if hid.rects:
                    # belt and braces: erase where the drag picture was, in case it was captured anyway
                    k = SIZE / max(1, shot.width())
                    local = [(int((x0 - tl.x()) * k), int((y0 - tl.y()) * k), int((x1 - tl.x()) * k), int((y1 - tl.y()) * k))
                             for (x0, y0, x1, y1) in hid.rects]
                    raw = glass.inpaint_rects(raw, local)
                    shot = QPixmap.fromImage(glass.qimage_from_pil(raw))
            self._raw_backdrop = raw
            self.backdrop = glass.blur_pixmap(shot, 24)
        except Exception:
            self.backdrop = None
            self._raw_backdrop = None
        self.move(tl)
        self.hover = -1
        self.got_drag = False
        self.hub_armed = False  # drags start on the hub; don't flip until they leave it
        self.click_mode = paths is not None
        early = []
        if paths is None and sys.platform == "darwin":
            from . import platform_mac
            early = platform_mac.drag_files()
            if early:
                print(f"menu: {len(early)} file(s) from the drag pasteboard", flush=True)
        if paths is not None:
            self._load(paths)
        elif early:
            self._load(early)           # slices show at once; drop still comes via dragEnter
        else:
            self.paths, self.rings, self.ring_names = [], {}, []
            self.hub_text = "Drop here"
            for n in (4, 7):  # most common rings: render speculatively
                self._render(n)
        self._t = 0.0
        self._shape()
        self.show()
        self.raise_()
        self.anim.start()
        self.frame.start()
        if self.click_mode:
            # behave like a popup: a click anywhere outside dismisses it
            QTimer.singleShot(0, self.grabMouse)

    def close_menu(self):
        if self.isVisible():
            self.hide()
            self.frame.stop()
            self.hub_timer.stop()
            self.dismissed.emit()

    def hideEvent(self, e):
        self.frame.stop()
        self.hub_timer.stop()
        if QWidget.mouseGrabber() is self:
            self.releaseMouse()
        super().hideEvent(e)

    def _render(self, n: int):
        if n <= 0 or n in self.liquid or self._raw_backdrop is None:
            return
        self.liquid[n] = QImage()  # placeholder: in flight
        job = _RenderJob(self._serial, n, self._raw_backdrop)
        from .util import keep, release
        job.sig.done.connect(lambda *a, j=job: (release(j), self._rendered(*a)))
        QThreadPool.globalInstance().start(keep(job))

    def _rendered(self, serial: int, n: int, img: QImage, light: bool):
        if serial == self._serial:
            self.liquid[n] = img
            self.is_light = light
            self.update()

    def _load(self, paths: list[str]):
        paths = resolve_shortcuts(paths)
        self.paths = paths
        self.rings = {k: v for k, v in self.build_rings(paths).items() if v}
        self.ring_names = list(self.rings)
        if self.requested_ring and self.requested_ring in self.ring_names:
            self.ring_idx = self.ring_names.index(self.requested_ring)
        else:
            self.ring_idx = 0
        self.hub_text = self.describe(paths)
        for items in self.rings.values():
            self._render(len(items))
        self.spring = [0.0] * len(self.items)
        self._shape()
        self.update()

    def set_ring(self, name_or_idx: str | int):
        if isinstance(name_or_idx, str):
            if name_or_idx in self.ring_names:
                idx = self.ring_names.index(name_or_idx)
            else:
                return
        else:
            idx = int(name_or_idx)
        if 0 <= idx < len(self.ring_names) and idx != self.ring_idx:
            self.ring_idx = idx
            self.hover = -1
            self.spring = [0.0] * len(self.items)
            self._swap = 0.0
            self.swap_anim.start()
            self._shape()
            self.update()

    def _shape(self):
        """No compositor (XFCE etc.): cut the window to the menu's outline."""
        if not glass.no_compositor():
            return
        c = QPointF(SIZE / 2, SIZE / 2)
        path = QPainterPath()
        path.addEllipse(c, R_HUB + 2, R_HUB + 2)
        n = len(self.items) or 0
        if n:
            for i in range(n):
                a0, a1 = angles(n, i)
                path = path.united(sector_path(c, R_IN - 2, R_OUT + 14, a0 - 1, a1 + 1))
        else:
            outer = QPainterPath()
            outer.addEllipse(c, R_OUT + 14, R_OUT + 14)
            path = path.united(outer)       # united, not added: odd-even fill would punch a hole
        glass.apply_shape(self, path)

    def next_ring(self):
        if len(self.ring_names) > 1:
            self.ring_idx = (self.ring_idx + 1) % len(self.ring_names)
            if self.hover != -2:
                self.hover = -1
            self.spring = [0.0] * len(self.items)
            self._swap = 0.0
            self.swap_anim.start()
            self._shape()
            self.update()

    def _set_t(self, v):
        self._t = float(v)
        self.update()

    def _set_swap(self, v):
        self._swap = float(v)
        self.update()

    def _tick(self):
        moved = False
        for i in range(len(self.spring)):
            target = 1.0 if i == self.hover else 0.0
            v = self.spring[i]
            nv = v + (target - v) * 0.32
            if abs(nv - target) < 0.003:
                nv = target
            if nv != v:
                self.spring[i] = nv
                moved = True
        ht = 1.0 if self.hover == -2 else 0.0
        nh = self.hub_spring + (ht - self.hub_spring) * 0.3
        if abs(nh - ht) < 0.003:
            nh = ht
        if nh != self.hub_spring:
            self.hub_spring = nh
            moved = True
        if moved:
            self.update()

    # ------------------------------------------------------------ geometry
    @property
    def items(self) -> list[Item]:
        if not self.ring_names:
            return []
        return self.rings[self.ring_names[self.ring_idx]]

    def _angles(self, n: int, i: int) -> tuple[float, float]:
        return angles(n, i)

    def hit(self, pos: QPointF) -> int:
        c = QPointF(SIZE / 2, SIZE / 2)
        dx, dy = pos.x() - c.x(), c.y() - pos.y()
        d = math.hypot(dx, dy)
        if d <= R_HUB + 4:
            return -2
        if d > R_OUT + 30 or not self.items:
            return -1
        ang = math.degrees(math.atan2(dy, dx)) % 360
        n = len(self.items)
        rel = (90 + 180.0 / n - ang) % 360
        return int(rel // (360.0 / n)) % n

    def _set_hover(self, h: int, pos: QPointF | None = None):
        if pos is not None:
            self.cursor_pos = QPointF(pos)
        if h != self.hover:
            self.hover = h
            if h >= 0:
                self.hub_armed = True  # visited a petal: hovering the hub may now flip rings
            if h == -2 and self.hub_armed and len(self.ring_names) > 1:
                self.hub_timer.setInterval(900)
                self.hub_timer.start()
            else:
                self.hub_timer.stop()
        self.update()

    # ------------------------------------------------------------ drag & drop
    @staticmethod
    def _local_paths(md) -> list[str]:
        if not md.hasUrls():
            return []
        return [u.toLocalFile() for u in md.urls() if u.isLocalFile() and u.toLocalFile()]

    def dragEnterEvent(self, e):
        paths = self._local_paths(e.mimeData())
        if not paths:
            e.ignore()
            return
        self.got_drag = True
        if resolve_shortcuts(paths) != self.paths:
            self._load(paths)
        e.setDropAction(Qt.CopyAction)  # never let a Shift(=move) drop delete the source
        e.accept()

    def dragMoveEvent(self, e):
        self._set_hover(self.hit(e.position()), e.position())
        e.setDropAction(Qt.CopyAction)
        e.accept()

    def dragLeaveEvent(self, e):
        self._set_hover(-1)

    def dropEvent(self, e):
        idx = self.hit(e.position())
        items = self.items
        if 0 <= idx < len(items):
            e.setDropAction(Qt.CopyAction)
            e.accept()
            item, paths = items[idx], list(self.paths)
            self.hide()
            # return to Explorer's drag loop immediately; do the work after
            QTimer.singleShot(0, lambda: self.activated.emit(item, paths))
        else:
            e.ignore()
            self.close_menu()

    # ------------------------------------------------------------ click mode
    def mouseMoveEvent(self, e):
        if self.click_mode:
            self._set_hover(self.hit(e.position()), e.position())

    def mouseReleaseEvent(self, e):
        if not self.click_mode:
            return
        if e.button() == Qt.RightButton:
            self.close_menu()
            return
        idx = self.hit(e.position())
        if idx == -2:
            self.next_ring()
        elif 0 <= idx < len(self.items):
            item, paths = self.items[idx], list(self.paths)
            self.hide()
            QTimer.singleShot(0, lambda: self.activated.emit(item, paths))
        else:
            self.close_menu()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close_menu()
        elif e.key() in (Qt.Key_Tab, Qt.Key_Shift):
            self.next_ring()

    def leaveEvent(self, e):
        if self.click_mode:
            self._set_hover(-1)

    # ------------------------------------------------------------ painting
    def _text_colors(self) -> tuple[QColor, QColor, QColor]:
        # Always use crisp, glowing white text with deep ambient shadow on frosted glass
        fg = QColor(255, 255, 255, 245)
        fg_dim = QColor(215, 230, 255, 220)
        shadow_col = QColor(0, 0, 0, 180)
        return fg, fg_dim, shadow_col

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        c = QPointF(SIZE / 2, SIZE / 2)
        t = self._t
        p.setOpacity(min(1.0, max(0.0, t * 1.5)))
        p.translate(c)
        s = 0.80 + 0.20 * t
        p.scale(s, s)
        p.translate(-c)

        items = self.items
        n = len(items)
        img = self.liquid.get(n) if n else (self.liquid.get(4) or self.liquid.get(7))
        have_liquid = img is not None and not img.isNull()

        if have_liquid:
            p.drawImage(0, 0, img)
        else:
            self._paint_fallback(p, c, n)

        fg, fg_dim, shadow_col = self._text_colors()
        rot = (1 - self._swap) * -22
        for i, it in enumerate(items):
            a0, a1 = angles(n, i)
            h = self.spring[i] if i < len(self.spring) else 0.0
            if h > 0.001:
                self._paint_hover(p, c, a0, a1, h, img if have_liquid else None)
            self._petal_label(p, c, it, (a0 + a1) / 2 + rot, (R_IN + R_OUT) / 2 + h * 4, h,
                              fg, shadow_col)
        if not n and self.paths:
            self._paint_unsupported(p, c, fg, fg_dim, shadow_col)

        self._paint_hub(p, c, fg, fg_dim, shadow_col)

    def _paint_unsupported(self, p: QPainter, c: QPointF, fg: QColor, fg_dim: QColor,
                           shadow_col: QColor):
        """Nothing to offer: say so in the top band, clear of the cursor and the drag image."""
        ext = Path(self.paths[0]).suffix.lower() or "this file"
        f = QFont(ui_family(True))
        f.setPixelSize(13)
        f.setBold(True)
        p.setFont(f)
        r_mid = (R_IN + R_OUT) / 2
        self._text(p, QRectF(c.x() - R_OUT, c.y() - r_mid - 18, 2 * R_OUT, 18),
                   f"Can't convert {ext}", fg, shadow_col)
        f.setPixelSize(10)
        f.setBold(False)
        p.setFont(f)
        self._text(p, QRectF(c.x() - R_OUT, c.y() - r_mid + 1, 2 * R_OUT, 16),
                   "Images · PDF · Word · Text", fg_dim, shadow_col)

    def _paint_fallback(self, p: QPainter, c: QPointF, n: int):
        hub = QPainterPath()
        hub.addEllipse(c, R_HUB, R_HUB)
        glass.paint_glass(p, hub, self.backdrop, QPointF(0, 0), tint=QColor(18, 14, 28, 140),
                          rainbow_alpha=150, highlight=1.3)
        for i in range(n):
            a0, a1 = angles(n, i)
            glass.paint_glass(p, sector_path(c, R_IN, R_OUT, a0, a1), self.backdrop, QPointF(0, 0),
                              tint=QColor(18, 14, 28, 110), rainbow_alpha=140)

    def _paint_hover(self, p: QPainter, c: QPointF, a0: float, a1: float, h: float, img: QImage | None):
        mid = math.radians((a0 + a1) / 2)
        r_mid = (R_IN + R_OUT) / 2
        pc = QPointF(c.x() + r_mid * math.cos(mid), c.y() - r_mid * math.sin(mid))
        k = 1 + 0.07 * h                     # elastic "pop" towards the cursor
        push = 6 * h
        off = QPointF(push * math.cos(mid), -push * math.sin(mid))
        path = sector_path(c, R_IN - 1, R_OUT + 1, a0, a1)
        p.save()
        p.translate(pc + off)
        p.scale(k, k)
        p.translate(-pc)
        # only the glass itself moves: the slice's own refraction, enlarged — no added light
        if img is not None:
            p.save()
            p.setClipPath(path)
            p.drawImage(0, 0, img)
            p.restore()
        else:
            glass.paint_glass(p, path, self.backdrop, QPointF(0, 0), tint=QColor(18, 14, 28, 120),
                              rainbow_alpha=140)
        p.restore()

    def _paint_hub(self, p: QPainter, c: QPointF, fg: QColor, fg_dim: QColor, shadow_col: QColor):
        # 1. Backing disc for center hub: guarantees zero bleed-through from desktop icons
        hub_path = QPainterPath()
        hub_path.addEllipse(c, R_HUB, R_HUB)
        glass.paint_glass(p, hub_path, self.backdrop, QPointF(0, 0),
                          tint=QColor(18, 14, 28, 140), rainbow_alpha=130, highlight=1.2)

        # 2. Iridescent border
        p.setPen(glass.iridescent_pen(c, 1.4, 180, angle=60))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, R_HUB - 0.5, R_HUB - 0.5)

        items = self.items
        hov = items[self.hover] if 0 <= self.hover < len(items) else None
        if hov is not None:
            top = hov.label if not hov.glyph else hov.label.title()
            sub = hov.hint or ""
        else:
            ring_name = self.ring_names[self.ring_idx] if self.ring_names else ""
            top = self.hub_text
            if len(self.ring_names) > 1:
                key_hint = "Shift / Ctrl" if sys.platform == "win32" else "⇧ / ⌃"
                sub = f"{ring_name.title()} · {key_hint}"
            else:
                sub = ring_name.title()

        f = QFont(ui_family(True))
        f.setPixelSize(14)
        f.setBold(True)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 0.4)
        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(f)
        while f.pixelSize() > 10 and fm.horizontalAdvance(top) > (2 * R_HUB - 12):
            f.setPixelSize(f.pixelSize() - 1)
            fm = QFontMetrics(f)
        p.setFont(f)
        rect_top = QRectF(c.x() - R_HUB + 4, c.y() - 19, 2 * R_HUB - 8, 20)
        self._text(p, rect_top, top, fg, shadow_col)

        f.setPixelSize(9.5)
        f.setBold(False)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 0.2)
        p.setFont(f)
        rect_sub = QRectF(c.x() - R_HUB + 4, c.y() + 2, 2 * R_HUB - 8, 28)
        self._text(p, rect_sub, sub, fg_dim, shadow_col,
                   Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap)

    @staticmethod
    def _text(p: QPainter, r: QRectF, text: str, col: QColor, shadow: QColor | None,
              flags=Qt.AlignCenter):
        if shadow is not None:
            p.setPen(shadow)
            # Ambient text shadow in multiple offsets for maximum legibility on any background:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (0, 1.5)):
                p.drawText(r.translated(dx, dy), flags, text)
        p.setPen(col)
        p.drawText(r, flags, text)

    def _petal_label(self, p: QPainter, c: QPointF, it: Item, ang: float, r: float,
                     h: float, fg: QColor, shadow_col: QColor):
        rad = math.radians(ang)
        push = 6 * h
        pt = QPointF(c.x() + (r + push) * math.cos(rad), c.y() - (r + push) * math.sin(rad))
        p.save()
        p.setOpacity(p.opacity() * (0.25 + 0.75 * self._swap))

        col = QColor(255, 255, 255, 255) if h > 0.3 else fg

        n = len(self.items) or 1
        # Generous dynamic box width matching the actual angular arc of the slice:
        box_w = min(170.0, max(94.0, 580.0 / max(3, n)))
        from PySide6.QtGui import QFontMetrics
        f = QFont(ui_family(True))

        if it.glyph:
            # 1. Glyph (icon)
            f.setPixelSize(int(19 + 2 * h))
            p.setFont(f)
            glyph_rect = QRectF(pt.x() - box_w / 2, pt.y() - 25, box_w, 22)
            self._text(p, glyph_rect, it.glyph, col, shadow_col, Qt.AlignHCenter | Qt.AlignBottom)

            # 2. Text Label
            display_label = it.label
            f.setPixelSize(int(10.5 + h))
            f.setBold(True)
            f.setLetterSpacing(QFont.AbsoluteSpacing, 0.4)

            fm = QFontMetrics(f)
            words = display_label.split()
            # If multi-word and too wide for a single line, wrap cleanly into 2 lines:
            if len(words) > 1 and fm.horizontalAdvance(display_label) > box_w - 6:
                mid = len(words) // 2
                display_label = " ".join(words[:mid]) + "\n" + " ".join(words[mid:])
                box_h = 32
                label_rect = QRectF(pt.x() - box_w / 2, pt.y() + 1, box_w, box_h)
                flags = Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap
            else:
                while f.pixelSize() > 8.5 and fm.horizontalAdvance(display_label) > box_w - 6:
                    f.setPixelSize(f.pixelSize() - 1)
                    fm = QFontMetrics(f)
                box_h = 18
                label_rect = QRectF(pt.x() - box_w / 2, pt.y() + 2, box_w, box_h)
                flags = Qt.AlignCenter

            p.setFont(f)
            self._text(p, label_rect, display_label, col, shadow_col, flags)
        else:
            # Slices without glyph (e.g. JPG, PNG, WEBP, ZIP, TAR, GZIP)
            display_label = it.label
            f.setPixelSize(int(14 + 1.5 * h))
            f.setBold(True)
            f.setLetterSpacing(QFont.AbsoluteSpacing, 0.6)

            fm = QFontMetrics(f)
            while f.pixelSize() > 9.5 and fm.horizontalAdvance(display_label) > box_w - 6:
                f.setPixelSize(f.pixelSize() - 1)
                fm = QFontMetrics(f)

            p.setFont(f)
            label_rect = QRectF(pt.x() - box_w / 2, pt.y() - 14, box_w, 28)
            self._text(p, label_rect, display_label, col, shadow_col, Qt.AlignCenter)

        p.restore()
