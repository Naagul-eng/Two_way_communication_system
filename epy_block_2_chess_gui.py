"""Embedded Python Block: Chess.com-style GUI, full chess rules, clocks, radio sync.

Ports:  event_in  <- 'Chess Protocol' event_out
        command_out -> 'Chess Protocol' command_in
Chat:   chat_out -> Transfer Protocol command_in ; Transfer Protocol event_out -> chat_in
        (text chat uses the encrypted, ACK-based transfer protocol, like the original chat GUI)
echo_test=True  : ONE window controls BOTH colours (use for single-laptop channel-model testing)
echo_test=False : you only move your own colour; moves go over the radio to the other node
                  (the two nodes MUST have different my_addr values, e.g. 'A' and 'B')
"""
import html as _html
import json
import random
import time
import numpy as np
from gnuradio import gr
import pmt
from PyQt5 import QtWidgets, QtCore, QtGui

FILES = 'abcdefgh'
KN = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
KG = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
DIAG = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
ORTH = [(-1, 0), (1, 0), (0, -1), (0, 1)]

# (label, base seconds, increment seconds)
TCS = [("Bullet 1+0", 60, 0), ("Bullet 2+1", 120, 1), ("Blitz 3+0", 180, 0),
       ("Blitz 3+1", 180, 1), ("Blitz 5+0", 300, 0), ("Rapid 10+0", 600, 0),
       ("Rapid 15+10", 900, 10), ("Classical 30+0", 1800, 0)]


def inb(r, c):
    return 0 <= r < 8 and 0 <= c < 8


def sq_name(r, c):
    return FILES[c] + str(8 - r)


def uci(m):
    return sq_name(m[0], m[1]) + sq_name(m[2], m[3]) + (m[4] or '')


class Position:
    """Row 0 = rank 8 (black side), row 7 = rank 1. Uppercase = white."""

    def __init__(self):
        self.board = [list('rnbqkbnr'), list('pppppppp')] + [['.'] * 8 for _ in range(4)] + \
                     [list('PPPPPPPP'), list('RNBQKBNR')]
        self.turn = 'w'
        self.castle = set('KQkq')
        self.ep = None
        self.half = 0
        self.full = 1

    def copy(self):
        n = Position.__new__(Position)
        n.board = [row[:] for row in self.board]
        n.turn = self.turn
        n.castle = set(self.castle)
        n.ep = self.ep
        n.half = self.half
        n.full = self.full
        return n

    def key(self):
        return (''.join(''.join(r) for r in self.board), self.turn,
                ''.join(sorted(self.castle)), self.ep)

    def find_king(self, color):
        k = 'K' if color == 'w' else 'k'
        for r in range(8):
            for c in range(8):
                if self.board[r][c] == k:
                    return r, c
        return None

    def attacked(self, r, c, by):
        b = self.board
        white = (by == 'w')
        pr = r + 1 if white else r - 1
        pawn = 'P' if white else 'p'
        for dc in (-1, 1):
            if inb(pr, c + dc) and b[pr][c + dc] == pawn:
                return True
        kn = 'N' if white else 'n'
        for dr, dc in KN:
            rr, cc = r + dr, c + dc
            if inb(rr, cc) and b[rr][cc] == kn:
                return True
        kg = 'K' if white else 'k'
        for dr, dc in KG:
            rr, cc = r + dr, c + dc
            if inb(rr, cc) and b[rr][cc] == kg:
                return True
        for dirs, pieces in ((DIAG, 'BQ'), (ORTH, 'RQ')):
            for dr, dc in dirs:
                rr, cc = r + dr, c + dc
                while inb(rr, cc):
                    p = b[rr][cc]
                    if p != '.':
                        if p.isupper() == white and p.upper() in pieces:
                            return True
                        break
                    rr += dr
                    cc += dc
        return False

    def in_check(self):
        kr, kc = self.find_king(self.turn)
        return self.attacked(kr, kc, 'b' if self.turn == 'w' else 'w')

    @staticmethod
    def _promo(out, r, c, rr, cc, last):
        if rr == last:
            for pr in 'qrbn':
                out.append((r, c, rr, cc, pr))
        else:
            out.append((r, c, rr, cc, ''))

    def pseudo(self):
        out = []
        b = self.board
        white = self.turn == 'w'
        for r in range(8):
            for c in range(8):
                p = b[r][c]
                if p == '.' or p.isupper() != white:
                    continue
                t = p.upper()
                if t == 'P':
                    d = -1 if white else 1
                    start = 6 if white else 1
                    last = 0 if white else 7
                    rr = r + d
                    if inb(rr, c) and b[rr][c] == '.':
                        self._promo(out, r, c, rr, c, last)
                        if r == start and b[r + 2 * d][c] == '.':
                            out.append((r, c, r + 2 * d, c, ''))
                    for dc in (-1, 1):
                        cc = c + dc
                        if not inb(rr, cc):
                            continue
                        tg = b[rr][cc]
                        if tg != '.' and tg.isupper() != white:
                            self._promo(out, r, c, rr, cc, last)
                        elif tg == '.' and self.ep == (rr, cc):
                            out.append((r, c, rr, cc, ''))
                elif t == 'N' or t == 'K':
                    for dr, dc in (KN if t == 'N' else KG):
                        rr, cc = r + dr, c + dc
                        if inb(rr, cc) and (b[rr][cc] == '.' or b[rr][cc].isupper() != white):
                            out.append((r, c, rr, cc, ''))
                    if t == 'K':
                        row = 7 if white else 0
                        opp = 'b' if white else 'w'
                        if r == row and c == 4 and not self.attacked(row, 4, opp):
                            rook = 'R' if white else 'r'
                            ks, qs = ('K', 'Q') if white else ('k', 'q')
                            if (ks in self.castle and b[row][5] == '.' and b[row][6] == '.'
                                    and b[row][7] == rook
                                    and not self.attacked(row, 5, opp)
                                    and not self.attacked(row, 6, opp)):
                                out.append((row, 4, row, 6, ''))
                            if (qs in self.castle and b[row][3] == '.' and b[row][2] == '.'
                                    and b[row][1] == '.' and b[row][0] == rook
                                    and not self.attacked(row, 3, opp)
                                    and not self.attacked(row, 2, opp)):
                                out.append((row, 4, row, 2, ''))
                else:
                    dirs = DIAG if t == 'B' else ORTH if t == 'R' else DIAG + ORTH
                    for dr, dc in dirs:
                        rr, cc = r + dr, c + dc
                        while inb(rr, cc):
                            tg = b[rr][cc]
                            if tg == '.':
                                out.append((r, c, rr, cc, ''))
                            else:
                                if tg.isupper() != white:
                                    out.append((r, c, rr, cc, ''))
                                break
                            rr += dr
                            cc += dc
        return out

    def make(self, m):
        fr, fc, tr, tc, pr = m
        n = self.copy()
        b = n.board
        p = b[fr][fc]
        cap = b[tr][tc]
        white = p.isupper()
        t = p.upper()
        b[fr][fc] = '.'
        if t == 'P' and cap == '.' and fc != tc:      # en passant capture
            b[fr][tc] = '.'
            cap = 'x'
        if pr:
            p = pr.upper() if white else pr.lower()
        b[tr][tc] = p
        if t == 'K' and abs(tc - fc) == 2:            # castling: move the rook
            if tc == 6:
                b[tr][5], b[tr][7] = b[tr][7], '.'
            else:
                b[tr][3], b[tr][0] = b[tr][0], '.'
        if t == 'K':
            n.castle -= set('KQ') if white else set('kq')
        corners = {(7, 0): 'Q', (7, 7): 'K', (0, 0): 'q', (0, 7): 'k'}
        for sq in ((fr, fc), (tr, tc)):
            if sq in corners:
                n.castle.discard(corners[sq])
        n.ep = ((fr + tr) // 2, fc) if (t == 'P' and abs(tr - fr) == 2) else None
        n.half = 0 if (t == 'P' or cap != '.') else self.half + 1
        if not white:
            n.full += 1
        n.turn = 'b' if white else 'w'
        return n

    def legal(self):
        res = []
        me = self.turn
        opp = 'b' if me == 'w' else 'w'
        for m in self.pseudo():
            n = self.make(m)
            kr, kc = n.find_king(me)
            if not n.attacked(kr, kc, opp):
                res.append(m)
        return res

    def insufficient(self):
        pcs = [(p, r, c) for r in range(8) for c in range(8)
               for p in [self.board[r][c]] if p not in '.kK']
        if not pcs:
            return True
        if any(p.upper() in 'PRQ' for p, _, _ in pcs):
            return False
        if len(pcs) == 1:
            return True
        return all(p.upper() == 'B' for p, _, _ in pcs) and len({(r + c) % 2 for _, r, c in pcs}) == 1

    def san(self, m, legal):
        fr, fc, tr, tc, pr = m
        p = self.board[fr][fc]
        t = p.upper()
        if t == 'K' and abs(tc - fc) == 2:
            s = 'O-O' if tc == 6 else 'O-O-O'
        else:
            cap = self.board[tr][tc] != '.' or (t == 'P' and fc != tc)
            if t == 'P':
                s = (FILES[fc] + 'x' if cap else '') + sq_name(tr, tc)
                if pr:
                    s += '=' + pr.upper()
            else:
                s = t
                others = [o for o in legal if o != m and self.board[o[0]][o[1]] == p
                          and o[2] == tr and o[3] == tc]
                if others:
                    if all(o[1] != fc for o in others):
                        s += FILES[fc]
                    elif all(o[0] != fr for o in others):
                        s += str(8 - fr)
                    else:
                        s += sq_name(fr, fc)
                s += ('x' if cap else '') + sq_name(tr, tc)
        n = self.make(m)
        if n.in_check():
            s += '#' if not n.legal() else '+'
        return s


def fmt_clock(ms):
    ms = max(0, ms)
    if ms < 20000:
        return "%d:%04.1f" % (int(ms // 60000), (ms % 60000) / 1000.0)
    s = int(ms // 1000)
    return "%d:%02d" % (s // 60, s % 60)


class BoardWidget(QtWidgets.QWidget):
    LIGHT = QtGui.QColor('#ebecd0')
    DARK = QtGui.QColor('#739552')

    def __init__(self, g):
        super().__init__()
        self.g = g
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setMinimumSize(320, 320)
        self.drag = False
        self.drag_pos = None
        self.press_sq = None
        self.cache = {}

    def geom(self):
        s = min(self.width(), self.height())
        return (self.width() - s) / 2.0, (self.height() - s) / 2.0, s / 8.0

    def disp(self, r, c):
        return (7 - r, 7 - c) if self.g.flipped else (r, c)

    def sq_at(self, x, y):
        ox, oy, cell = self.geom()
        dc = int((x - ox) // cell)
        dr = int((y - oy) // cell)
        if not (0 <= dr < 8 and 0 <= dc < 8):
            return None
        return (7 - dr, 7 - dc) if self.g.flipped else (dr, dc)

    def piece_path(self, piece, cell):
        key = (piece, int(cell))
        if key in self.cache:
            return self.cache[key]
        glyph = {'k': '\u265A', 'q': '\u265B', 'r': '\u265C',
                 'b': '\u265D', 'n': '\u265E', 'p': '\u265F'}[piece.lower()]
        f = QtGui.QFont()
        fam = ['DejaVu Sans', 'Segoe UI Symbol', 'Noto Sans Symbols2', 'FreeSerif', 'Arial Unicode MS']
        if hasattr(f, 'setFamilies'):
            f.setFamilies(fam)
        else:
            f.setFamily(fam[0])
        f.setPixelSize(max(8, int(cell * 0.80)))
        path = QtGui.QPainterPath()
        path.addText(0, 0, f, glyph)
        if path.isEmpty():
            path.addText(0, 0, f, piece.upper())
        br = path.boundingRect()
        path.translate(-br.center().x(), -br.center().y())
        self.cache[key] = path
        return path

    def draw_piece(self, p, piece, cx, cy, cell):
        path = self.piece_path(piece, cell)
        p.save()
        p.translate(cx, cy)
        if piece.isupper():
            p.setBrush(QtGui.QColor('#ffffff'))
            p.setPen(QtGui.QPen(QtGui.QColor('#2a2a2a'), max(1.0, cell * 0.03)))
        else:
            p.setBrush(QtGui.QColor('#262626'))
            p.setPen(QtGui.QPen(QtGui.QColor('#000000'), max(1.0, cell * 0.02)))
        p.drawPath(path)
        p.restore()

    def paintEvent(self, ev):
        g = self.g
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setRenderHint(QtGui.QPainter.TextAntialiasing)
        ox, oy, cell = self.geom()
        board = g.pos.board
        lm = g.last_move
        last_sqs = {(lm[0], lm[1]), (lm[2], lm[3])} if lm else set()
        check_sq = g.pos.find_king(g.pos.turn) if (g.pos.in_check() and g.active) or \
            (g.pos.in_check() and g.result.startswith('Checkmate')) else None
        targets = {(m[2], m[3]) for m in g.targets}
        font = QtGui.QFont()
        font.setPixelSize(max(8, int(cell * 0.17)))
        font.setBold(True)
        p.setFont(font)
        for r in range(8):
            for c in range(8):
                dr, dc = self.disp(r, c)
                rect = QtCore.QRectF(ox + dc * cell, oy + dr * cell, cell, cell)
                light = (r + c) % 2 == 0
                p.fillRect(rect, self.LIGHT if light else self.DARK)
                if (r, c) in last_sqs:
                    p.fillRect(rect, QtGui.QColor(255, 235, 0, 105))
                if g.selected == (r, c):
                    p.fillRect(rect, QtGui.QColor(255, 235, 0, 140))
                if check_sq == (r, c):
                    grad = QtGui.QRadialGradient(rect.center(), cell * 0.62)
                    grad.setColorAt(0.0, QtGui.QColor(255, 0, 0, 220))
                    grad.setColorAt(1.0, QtGui.QColor(255, 0, 0, 0))
                    p.fillRect(rect, QtGui.QBrush(grad))
                p.setPen(self.DARK if light else self.LIGHT)
                if dc == 0:
                    p.drawText(rect.adjusted(cell * 0.05, cell * 0.03, 0, 0),
                               QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, str(8 - r))
                if dr == 7:
                    p.drawText(rect.adjusted(0, 0, -cell * 0.06, -cell * 0.03),
                               QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom, FILES[c])
        for r in range(8):
            for c in range(8):
                piece = board[r][c]
                if piece == '.':
                    continue
                if self.drag and g.selected == (r, c):
                    continue
                dr, dc = self.disp(r, c)
                self.draw_piece(p, piece, ox + (dc + 0.5) * cell, oy + (dr + 0.5) * cell, cell)
        p.setPen(QtCore.Qt.NoPen)
        for (r, c) in targets:
            dr, dc = self.disp(r, c)
            cx, cy = ox + (dc + 0.5) * cell, oy + (dr + 0.5) * cell
            if board[r][c] == '.' and not any(m[2] == r and m[3] == c and m[0] != m[2] and
                                              board[m[0]][m[1]].upper() == 'P' and m[1] != m[3]
                                              for m in g.targets):
                p.setBrush(QtGui.QColor(0, 0, 0, 55))
                p.drawEllipse(QtCore.QPointF(cx, cy), cell * 0.16, cell * 0.16)
            else:
                p.setBrush(QtCore.Qt.NoBrush)
                p.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 55), cell * 0.09))
                p.drawEllipse(QtCore.QPointF(cx, cy), cell * 0.42, cell * 0.42)
                p.setPen(QtCore.Qt.NoPen)
        if self.drag and g.selected and self.drag_pos is not None:
            sr, sc = g.selected
            self.draw_piece(p, board[sr][sc], self.drag_pos.x(), self.drag_pos.y(), cell)
        p.end()

    def mousePressEvent(self, e):
        if e.button() != QtCore.Qt.LeftButton:
            return
        sq = self.sq_at(e.x(), e.y())
        self.press_sq = sq
        if sq is None:
            return
        self.g.click(*sq)
        if self.g.selected == sq:
            self.drag = True
            self.drag_pos = e.pos()
        self.update()

    def mouseMoveEvent(self, e):
        if self.drag:
            self.drag_pos = e.pos()
            self.update()

    def mouseReleaseEvent(self, e):
        if self.drag:
            self.drag = False
            sq = self.sq_at(e.x(), e.y())
            if sq is not None and sq != self.press_sq:
                self.g.click(*sq)
        self.update()


class PlayerBar(QtWidgets.QFrame):
    def __init__(self):
        super().__init__()
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        self.name = QtWidgets.QLabel('')
        self.name.setStyleSheet("font-weight:bold;background:transparent;")
        self.clock = QtWidgets.QLabel('0:00')
        self.clock.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.clock.setStyleSheet("font-size:26px;font-weight:bold;font-family:monospace;background:transparent;")
        lay.addWidget(self.name, 1)
        lay.addWidget(self.clock)
        self.set_active(False)

    def set_active(self, on):
        self.setStyleSheet("QFrame{background:%s;border-radius:4px;}" % ('#ffffff' if on else '#262421'))
        col = '#000000' if on else '#bbbbbb'
        self.name.setStyleSheet("font-weight:bold;background:transparent;color:%s;" % col)
        self.clock.setStyleSheet("font-size:26px;font-weight:bold;font-family:monospace;"
                                 "background:transparent;color:%s;" % col)


class ChessWindow(QtWidgets.QWidget):
    def __init__(self, g):
        super().__init__()
        self.g = g
        self.setWindowTitle("Radio Chess | Node %s vs %s" % (g.my_addr, g.peer_addr))
        self.resize(1150, 800)
        self.setMinimumSize(760, 560)
        self.setStyleSheet(
            "QWidget{background:#312e2b;color:#ffffff;font-size:14px;}"
            "QPushButton{background:#454240;border:none;padding:9px 12px;border-radius:4px;font-weight:bold;}"
            "QPushButton:hover{background:#5a5755;}"
            "QComboBox{background:#454240;padding:5px;border-radius:4px;}"
            "QComboBox QAbstractItemView{background:#262421;selection-background-color:#739552;}"
            "QTextBrowser{background:#262421;border:none;}"
            "QLineEdit{background:#262421;border:none;border-radius:4px;padding:7px;}")
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)
        self.board = BoardWidget(g)
        root.addWidget(self.board, 1)
        panel = QtWidgets.QWidget()
        panel.setMinimumWidth(270)
        panel.setMaximumWidth(360)
        v = QtWidgets.QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        self.top = PlayerBar()
        self.bottom = PlayerBar()
        self.moves = QtWidgets.QTextBrowser()
        self.chat_view = QtWidgets.QTextBrowser()
        self.chat_input = QtWidgets.QLineEdit()
        self.chat_input.setPlaceholderText("Chat with opponent (Enter to send)")
        self.chat_input.setMaxLength(500)
        self.chat_input.returnPressed.connect(self.on_chat_send)
        b_send = QtWidgets.QPushButton("Send")
        b_send.clicked.connect(self.on_chat_send)
        chat_row = QtWidgets.QHBoxLayout()
        chat_row.addWidget(self.chat_input, 1)
        chat_row.addWidget(b_send)
        self.status = QtWidgets.QLabel('')
        self.status.setWordWrap(True)
        self.info = QtWidgets.QLabel('')
        self.info.setWordWrap(True)
        self.info.setStyleSheet("color:#aaaaaa;font-size:12px;")
        self.tc_combo = QtWidgets.QComboBox()
        for name, b, i in TCS:
            self.tc_combo.addItem(name)
        idx = next((k for k, t in enumerate(TCS) if t[1] == g.base and t[2] * 1000 == g.inc), -1)
        if idx < 0:
            self.tc_combo.addItem("Custom %g+%d" % (g.base / 60.0, g.inc // 1000))
            idx = self.tc_combo.count() - 1
            self.custom = (g.base, g.inc // 1000)
        else:
            self.custom = None
        self.tc_combo.setCurrentIndex(idx)
        self.color_combo = QtWidgets.QComboBox()
        self.color_combo.addItems(["Play as White", "Play as Black", "Random"])
        self.color_combo.setCurrentIndex(0 if g.my_color == 'w' else 1)
        b_new = QtWidgets.QPushButton("New Game")
        b_res = QtWidgets.QPushButton("Resign")
        b_flip = QtWidgets.QPushButton("Flip Board")
        b_draw = QtWidgets.QPushButton("Offer Draw")
        b_take = QtWidgets.QPushButton("Takeback")
        b_draw.clicked.connect(lambda: g.request('draw_offer'))
        b_take.clicked.connect(lambda: g.request('takeback_req'))
        b_new.clicked.connect(self.on_new)
        b_res.clicked.connect(g.resign)
        b_flip.clicked.connect(self.on_flip)
        v.addWidget(self.top)
        v.addWidget(self.moves, 3)
        v.addWidget(self.chat_view, 2)
        v.addLayout(chat_row)
        v.addWidget(self.bottom)
        v.addWidget(self.status)
        v.addWidget(self.tc_combo)
        v.addWidget(self.color_combo)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(b_new)
        row.addWidget(b_res)
        row.addWidget(b_flip)
        v.addLayout(row)
        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(b_draw)
        row2.addWidget(b_take)
        v.addLayout(row2)
        v.addWidget(self.info)
        root.addWidget(panel, 0)

    def on_new(self):
        i = self.tc_combo.currentIndex()
        if i < len(TCS):
            base, inc = TCS[i][1], TCS[i][2]
        else:
            base, inc = self.custom
        c = self.color_combo.currentIndex()
        color = 'w' if c == 0 else 'b' if c == 1 else random.choice('wb')
        self.g.new_game(color, base, inc)

    def on_chat_send(self):
        text = self.chat_input.text()
        self.chat_input.clear()
        self.g.send_chat(text)

    def update_chat(self):
        rows = []
        for m in self.g.chat_log[-60:]:
            t = _html.escape(m['text'])
            if m['who'] == 'me':
                st = ("<span style='color:#888;font-size:11px'> (%s)</span>" % _html.escape(m['status'])) if m['status'] else ''
                rows.append("<p style='margin:2px'><b style='color:#9ccc65'>You:</b> %s%s</p>" % (t, st))
            elif m['who'] == 'peer':
                rows.append("<p style='margin:2px'><b style='color:#64b5f6'>%s:</b> %s</p>" % (_html.escape(m.get('tag', 'Opponent')), t))
            else:
                rows.append("<p style='margin:2px;color:#888'><i>%s</i></p>" % t)
        self.chat_view.setHtml(''.join(rows))
        sb = self.chat_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_flip(self):
        self.g.flipped = not self.g.flipped
        self.refresh()

    def sync_combos(self):
        for k, t in enumerate(TCS):
            if t[1] == self.g.base and t[2] * 1000 == self.g.inc:
                self.tc_combo.setCurrentIndex(k)
                break
        self.color_combo.setCurrentIndex(0 if self.g.my_color == 'w' else 1)

    def refresh(self):
        g = self.g
        self.board.update()
        bottom_c = 'b' if g.flipped else 'w'
        top_c = 'w' if g.flipped else 'b'
        for bar, col in ((self.top, top_c), (self.bottom, bottom_c)):
            who = ("You (%s)" % g.my_addr) if col == g.my_color else ("Opponent (%s)" % g.peer_addr)
            bar.name.setText("%s — %s" % (who, 'White' if col == 'w' else 'Black'))
        rows = []
        for i in range(0, len(g.sans), 2):
            w = g.sans[i]
            b = g.sans[i + 1] if i + 1 < len(g.sans) else ''
            rows.append("<tr><td style='color:#888'>%d.&nbsp;</td><td><b>%s</b>&nbsp;&nbsp;</td>"
                        "<td><b>%s</b></td></tr>" % (i // 2 + 1, w, b))
        res = ("<p style='color:#ffd54f'><b>%s</b></p>" % g.result) if g.result else ''
        self.moves.setHtml("<table cellspacing='4'>%s</table>%s" % (''.join(rows), res))
        sb = self.moves.verticalScrollBar()
        sb.setValue(sb.maximum())
        self.status.setText(g.status_text())
        self.info.setText("%s | You: %s | %s" % (g.tc_label(), 'White' if g.my_color == 'w' else 'Black',
                                                  "Loopback test: both sides playable here" if g.echo_test
                                                  else "Radio link: you move your colour only"))
        self.update_clocks()

    def update_clocks(self):
        g = self.g
        bottom_c = 'b' if g.flipped else 'w'
        top_c = 'w' if g.flipped else 'b'
        running = g.active and len(g.history) >= 2
        for bar, col in ((self.top, top_c), (self.bottom, bottom_c)):
            bar.clock.setText(fmt_clock(g.clock[col]))
            bar.set_active(running and g.pos.turn == col)


class blk(gr.basic_block):
    def __init__(self, my_addr='A', peer_addr='B', time_control='5+0', color_choice='white',
                 show_gui=True, echo_test=True):
        gr.basic_block.__init__(self, name='Chess GUI', in_sig=None, out_sig=None)
        self.my_addr = str(my_addr)
        self.peer_addr = str(peer_addr)
        self.show_gui = show_gui
        self.echo_test = bool(echo_test)
        self.message_port_register_in(pmt.intern('event_in'))
        self.set_msg_handler(pmt.intern('event_in'), self.handle_event)
        self.message_port_register_out(pmt.intern('command_out'))
        self.message_port_register_in(pmt.intern('chat_in'))
        self.set_msg_handler(pmt.intern('chat_in'), self.handle_chat_event)
        self.message_port_register_out(pmt.intern('chat_out'))
        self.events = []
        self.chat_events = []
        self.chat_log = []
        self.chat_queue = []
        self.chat_busy = False
        self.chat_pending = {}
        self.chat_id = 0
        try:
            a, b = str(time_control).split('+')
            base, inc = int(float(a) * 60), int(float(b))
        except Exception:
            base, inc = 300, 0
        cc = str(color_choice).lower()
        my = 'w' if cc.startswith('w') else 'b' if cc.startswith('b') else random.choice('wb')
        self.window = None
        self.pending_new = None
        self.pending_move = None
        self.start_game(my, base, inc, int(time.time() * 1000) % 1000000000)
        if self.show_gui:
            self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
            self.window = ChessWindow(self)
            self.window.show()
            self.window.refresh()
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.on_tick)
            self.timer.start(100)

    # ---------------- game state ----------------
    def start_game(self, my_color, base, inc, gid):
        self.pos = Position()
        self.history = []
        self.sans = []
        self.reps = {self.pos.key(): 1}
        self.base = base
        self.inc = inc * 1000
        self.clock = {'w': base * 1000.0, 'b': base * 1000.0}
        self.active = True
        self.result = ''
        self.last_move = None
        self.selected = None
        self.targets = []
        self.legal_cache = self.pos.legal()
        self.my_color = my_color
        self.flipped = (my_color == 'b')
        self.gid = gid
        self.pending_new = None
        self.pending_move = None
        self.snapshots = []
        self.epoch = 0
        self.pending_req = None
        self.note = ''
        self.answered = {}
        self.asking = False
        self.last_tick = time.monotonic()
        if self.window:
            self.window.refresh()

    def tc_label(self):
        return "Time Control: %g+%d" % (self.base / 60.0, self.inc // 1000)

    def new_game(self, my_color, base, inc):
        gid = int(time.time() * 1000) % 1000000000
        self.start_game(my_color, base, inc, gid)
        if not self.echo_test:
            pk = {'type': 'new_game', 'gid': gid, 'host_color': my_color, 'base': base, 'inc': inc}
            self.pending_new = (pk, time.monotonic())
            self.send(pk)

    def can_move(self, color):
        return self.echo_test or color == self.my_color

    def status_text(self):
        if self.result:
            return self.result
        s = ("White" if self.pos.turn == 'w' else "Black") + " to move"
        if self.pos.in_check():
            s += " — CHECK!"
        if not self.echo_test:
            s += "  (your turn)" if self.pos.turn == self.my_color else "  (waiting for opponent)"
        if len(self.history) < 2:
            s += "\nClocks start after both sides have moved."
        if self.note:
            s += "\n" + self.note
        return s

    def finish(self, text):
        self.active = False
        self.result = text
        self.selected = None
        self.targets = []

    def check_end(self):
        if not self.legal_cache:
            if self.pos.in_check():
                self.finish("Checkmate — %s wins" % ("Black" if self.pos.turn == 'w' else "White"))
            else:
                self.finish("Draw by stalemate")
        elif self.pos.insufficient():
            self.finish("Draw by insufficient material")
        elif self.pos.half >= 100:
            self.finish("Draw by fifty-move rule")
        elif self.reps.get(self.pos.key(), 0) >= 3:
            self.finish("Draw by threefold repetition")

    def tick(self):
        now = time.monotonic()
        dt = now - self.last_tick
        self.last_tick = now
        if self.active and len(self.history) >= 2:
            side = self.pos.turn
            self.clock[side] -= dt * 1000.0
            if self.clock[side] <= 0:
                self.clock[side] = 0
                self.finish("%s wins on time" % ("Black" if side == 'w' else "White"))
                if self.window:
                    self.window.refresh()

    def apply_move(self, m, net=False):
        if not self.active or m not in self.legal_cache:
            return False
        self.tick()
        self.snapshots.append((self.pos, self.last_move, dict(self.clock)))
        self.note = ''
        self.pending_req = None
        mover = self.pos.turn
        if len(self.history) >= 2:
            self.clock[mover] += self.inc
        san = self.pos.san(m, self.legal_cache)
        self.pos = self.pos.make(m)
        self.history.append(uci(m))
        self.sans.append(san)
        k = self.pos.key()
        self.reps[k] = self.reps.get(k, 0) + 1
        self.last_move = m
        self.selected = None
        self.targets = []
        self.legal_cache = self.pos.legal()
        self.check_end()
        if net:
            self.pending_move = None
        else:
            self.send_move()
        if self.window:
            self.window.refresh()
        return True

    def ask_promotion(self, cand):
        menu = QtWidgets.QMenu(self.window)
        acts = {}
        for name, ch in (("Queen", 'q'), ("Rook", 'r'), ("Bishop", 'b'), ("Knight", 'n')):
            acts[menu.addAction(name)] = ch
        a = menu.exec_(QtGui.QCursor.pos())
        if a is None:
            return None
        return next((m for m in cand if m[4] == acts[a]), None)

    def click(self, r, c):
        if not self.active:
            return
        if self.pending_req and self.pending_req['pk']['type'] == 'takeback_req':
            self.note = 'Waiting for takeback answer...'
            return
        p = self.pos.board[r][c]
        if self.selected is not None:
            cand = [m for m in self.targets if m[2] == r and m[3] == c]
            if cand:
                m = cand[0] if len(cand) == 1 else self.ask_promotion(cand)
                if m is not None:
                    self.apply_move(m)
                if self.window:
                    self.window.refresh()
                return
        if p != '.' and p.isupper() == (self.pos.turn == 'w') and self.can_move(self.pos.turn):
            self.selected = (r, c)
            self.targets = [m for m in self.legal_cache if m[0] == r and m[1] == c]
        else:
            self.selected = None
            self.targets = []
        if self.window:
            self.window.refresh()

    def resign(self):
        if not self.active:
            return
        side = self.pos.turn if self.echo_test else self.my_color
        self.finish("%s resigned — %s wins" % ("White" if side == 'w' else "Black",
                                               "Black" if side == 'w' else "White"))
        if not self.echo_test:
            self.send({'type': 'resign', 'gid': self.gid, 'color': side})
        if self.window:
            self.window.refresh()

    # ---------------- draw offers / takebacks ----------------
    def undo_to(self, L):
        while len(self.history) > L and self.snapshots:
            k = self.pos.key()
            self.reps[k] = self.reps.get(k, 1) - 1
            self.history.pop()
            self.sans.pop()
            self.pos, self.last_move, self.clock = self.snapshots.pop()
        self.legal_cache = self.pos.legal()
        self.selected = None
        self.targets = []
        self.active = True
        self.result = ''
        self.pending_move = None
        self.pending_req = None
        self.last_tick = time.monotonic()

    def takeback_target(self, requester):
        n = len(self.history)
        if n == 0:
            return None
        L = n - 2 if self.pos.turn == requester else n - 1
        return L if L >= 0 else None

    def ask_user(self, text):
        self.asking = True
        try:
            box = QtWidgets.QMessageBox
            return box.question(self.window, "Radio Chess", text,
                                box.Yes | box.No, box.No) == box.Yes
        finally:
            self.asking = False
            self.last_tick = time.monotonic()

    def request(self, kind):
        if not self.active or self.pending_req or self.asking:
            return
        n = len(self.history)
        by = self.my_color if not self.echo_test else ('b' if self.pos.turn == 'w' else 'w')
        if kind == 'draw_offer' and self.echo_test:
            by = self.pos.turn
        if kind == 'takeback_req' and self.takeback_target(by) is None:
            self.note = "Nothing to take back."
            self.window.refresh()
            return
        pk = {'type': kind, 'gid': self.gid, 'n': n, 'by': by}
        if self.echo_test:
            if kind == 'draw_offer':
                if self.ask_user("%s offers a draw. Accept?" % ("White" if by == 'w' else "Black")):
                    self.finish("Draw by agreement")
                else:
                    self.note = "Draw declined."
            else:
                if self.ask_user("%s asks to take back their last move. Allow?" %
                                 ("White" if by == 'w' else "Black")):
                    self.undo_to(self.takeback_target(by))
                    self.epoch += 1
                else:
                    self.note = "Takeback declined."
        else:
            self.pending_req = {'pk': pk, 't': time.monotonic(), 'tries': 0}
            self.note = "Draw offer sent..." if kind == 'draw_offer' else "Takeback request sent..."
            self.send(dict(pk))
        self.window.refresh()

    def on_request(self, pk):
        t = pk['type']
        n = pk.get('n')
        key = (t, n, self.epoch)
        if key in self.answered:
            self.send(dict(self.answered[key]))
            return
        if self.asking or not self.active or n != len(self.history):
            return
        by = pk.get('by')
        who = "Your opponent"
        if t == 'draw_offer':
            ok = self.ask_user("%s offers a draw. Accept?" % who)
            L = 0
            if ok:
                self.finish("Draw by agreement")
        else:
            L = self.takeback_target(by)
            ok = False
            if L is not None:
                ok = self.ask_user("%s asks to take back their last move. Allow?" % who)
            if ok:
                self.undo_to(L)
                self.epoch += 1
        ans = {'type': 'draw_ans' if t == 'draw_offer' else 'takeback_ans', 'gid': self.gid,
               'n': n, 'ok': bool(ok), 'L': L if L is not None else 0}
        self.answered[key] = ans
        self.send(dict(ans))
        self.window.refresh()

    def on_answer(self, pk):
        pr = self.pending_req
        want = 'draw_offer' if pk['type'] == 'draw_ans' else 'takeback_req'
        if not pr or pr['pk']['type'] != want or pk.get('gid') != self.gid or pk.get('n') != pr['pk']['n']:
            return
        self.pending_req = None
        if pk.get('ok'):
            if want == 'draw_offer':
                self.finish("Draw by agreement")
            elif len(self.history) == pk['n']:
                self.undo_to(int(pk.get('L', 0)))
                self.epoch += 1
                self.note = "Takeback accepted."
        else:
            self.note = "Opponent declined the %s." % ("draw offer" if want == 'draw_offer' else "takeback")
        self.window.refresh()

    # ---------------- radio side ----------------
    def send(self, d):
        d['chess'] = 1
        d['src'] = self.my_addr
        d['dst'] = self.peer_addr
        raw = json.dumps(d, separators=(',', ':')).encode('utf-8')
        try:
            self.message_port_pub(pmt.intern('command_out'),
                                  pmt.cons(pmt.PMT_NIL, pmt.init_u8vector(len(raw), list(raw))))
        except Exception:
            pass

    def send_move(self):
        n = len(self.history)
        start = max(0, n - 8)
        pk = {'type': 'move', 'gid': self.gid, 'start': start, 'moves': self.history[start:], 'ep': self.epoch,
              'clock': [int(self.clock['w']), int(self.clock['b'])]}
        if not self.echo_test:
            self.pending_move = (pk, n, time.monotonic())
        self.send(pk)

    @staticmethod
    def _bytes(msg):
        if pmt.is_pair(msg) and pmt.is_u8vector(pmt.cdr(msg)):
            return bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        return None

    def handle_event(self, msg):
        raw = self._bytes(msg)
        if raw is None:
            return
        try:
            ev = json.loads(raw.decode('utf-8'))
            if ev.get('direction') == 'peer_move':
                self.events.append(ev.get('data', {}))
        except ValueError:
            pass

    def on_packet(self, pk):
        if (self.echo_test and isinstance(pk, dict) and pk.get('chess') == 1 and pk.get('type') == 'chat'
                and pk.get('src') == self.my_addr and pk.get('dst') == self.peer_addr):
            self.on_loopback_chat(pk)
            return
        if not isinstance(pk, dict) or pk.get('chess') != 1 or pk.get('src') == self.my_addr \
                or pk.get('dst') != self.my_addr:
            return
        t = pk.get('type')
        if t == 'new_game':
            gid = pk.get('gid')
            if gid != self.gid:
                mine = 'b' if pk.get('host_color') == 'w' else 'w'
                self.start_game(mine, int(pk.get('base', 300)), int(pk.get('inc', 0)), gid)
                if self.window:
                    self.window.sync_combos()
                    self.window.refresh()
            self.send({'type': 'ack_new', 'gid': gid})
        elif t == 'ack_new':
            if self.pending_new and self.pending_new[0]['gid'] == pk.get('gid'):
                self.pending_new = None
        elif t == 'ack_move':
            if (self.pending_move and pk.get('gid') == self.gid
                    and pk.get('n', 0) >= self.pending_move[1]):
                self.pending_move = None
        elif t == 'resign':
            if pk.get('gid') == self.gid and self.active:
                s = pk.get('color')
                self.finish("%s resigned — %s wins" % ("White" if s == 'w' else "Black",
                                                       "Black" if s == 'w' else "White"))
                if self.window:
                    self.window.refresh()
        elif t in ('draw_offer', 'takeback_req'):
            if pk.get('gid') == self.gid:
                self.on_request(pk)
        elif t in ('draw_ans', 'takeback_ans'):
            self.on_answer(pk)
        elif t == 'move':
            if pk.get('gid') != self.gid or pk.get('ep', 0) != self.epoch:
                return
            start = pk.get('start', 0)
            moves = pk.get('moves', [])
            n = len(self.history)
            if start <= n < start + len(moves) and self.history[start:n] == moves[:n - start]:
                for u in moves[n - start:]:
                    m = next((x for x in self.legal_cache if uci(x) == u), None)
                    if m is None:
                        break
                    self.apply_move(m, net=True)
                clk = pk.get('clock')
                if clk and len(clk) == 2:
                    self.clock = {'w': float(clk[0]), 'b': float(clk[1])}
                    self.last_tick = time.monotonic()
            self.send({'type': 'ack_move', 'gid': self.gid, 'n': len(self.history)})

    # ---------------- text chat (via Transfer Protocol) ----------------
    def handle_chat_event(self, msg):
        raw = self._bytes(msg)
        if raw is None:
            return
        try:
            ev = json.loads(raw.decode('utf-8'))
            if isinstance(ev, dict):
                self.chat_events.append(ev)
        except ValueError:
            pass

    def send_chat(self, text):
        text = text.strip()[:500]
        if not text:
            return
        entry = {'who': 'me', 'text': text, 'status': 'queued'}
        self.chat_log.append(entry)
        if self.echo_test:
            # Loopback test: send over the chess channel (encrypt -> CRC -> RS -> QPSK -> channel
            # model -> receiver). The echo coming back proves the whole chain works.
            self.chat_id += 1
            entry['status'] = 'sending over radio loopback...'
            self.chat_pending[self.chat_id] = (entry, time.monotonic())
            self.send({'type': 'chat', 'id': self.chat_id, 'text': text})
        else:
            self.chat_queue.append(entry)
            self.pump_chat()
        self.refresh_chat()

    def pump_chat(self):
        if self.chat_busy or not self.chat_queue:
            return
        entry = self.chat_queue[0]
        entry['status'] = 'sending...'
        self.chat_busy = True
        raw = json.dumps({'cmd': 'send', 'kind': 'text', 'value': entry['text']}).encode('utf-8')
        try:
            self.message_port_pub(pmt.intern('chat_out'),
                                  pmt.cons(pmt.PMT_NIL, pmt.init_u8vector(len(raw), list(raw))))
        except Exception:
            pass

    def on_chat_event(self, e):
        d = e.get('direction')
        st = str(e.get('state', ''))
        kind = e.get('kind')
        active = st.startswith(('Sending', 'Receiving', 'Waiting', 'Retry'))
        if d == 'rx':
            if st.startswith('Complete'):
                if kind == 'text':
                    self.chat_log.append({'who': 'peer', 'text': str(e.get('text', '')), 'status': ''})
                else:
                    self.chat_log.append({'who': 'sys', 'text': '[peer sent %s: saved to receive folder]' % kind,
                                          'status': ''})
        elif d in ('tx', 'notice'):
            if d == 'tx' and (kind not in (None, 'text') or active):
                return
            if self.chat_busy and self.chat_queue:
                entry = self.chat_queue.pop(0)
                entry['status'] = ('delivered \u2713' if (d == 'tx' and st.startswith('Complete'))
                                   else 'failed: ' + st)
                self.chat_busy = False
                self.pump_chat()
        self.refresh_chat()

    def on_loopback_chat(self, pk):
        got = self.chat_pending.pop(pk.get('id'), None)
        if got is None:
            return
        entry, t0 = got
        entry['status'] = 'delivered \u2713 via radio loopback, %.1f s' % (time.monotonic() - t0)
        self.chat_log.append({'who': 'peer', 'text': str(pk.get('text', '')),
                              'status': '', 'tag': 'Opponent (loopback echo)'})
        self.refresh_chat()

    def refresh_chat(self):
        if self.window:
            self.window.update_chat()

    def on_tick(self):
        while self.events and not self.asking:
            self.on_packet(self.events.pop(0))
        while self.chat_events:
            self.on_chat_event(self.chat_events.pop(0))
        self.tick()
        now = time.monotonic()
        if self.pending_new and now - self.pending_new[1] > 2.0:
            self.pending_new = (self.pending_new[0], now)
            self.send(dict(self.pending_new[0]))
        if self.pending_move and now - self.pending_move[2] > 3.0:
            pk, n, _ = self.pending_move
            self.pending_move = (pk, n, now)
            self.send(dict(pk))
        for cid, (ent, t0) in list(self.chat_pending.items()):
            if now - t0 > 10.0:
                ent['status'] = 'no echo after 10 s: is the radio chain connected?'
                del self.chat_pending[cid]
                self.refresh_chat()
        pr = self.pending_req
        if pr and now - pr['t'] > 3.0:
            pr['t'] = now
            pr['tries'] += 1
            if pr['tries'] > 10:
                self.pending_req = None
                self.note = 'No response from opponent.'
            else:
                self.send(dict(pr['pk']))
        if self.window:
            self.window.update_clocks()
            self.window.status.setText(self.status_text())
