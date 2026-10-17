"""PyQt5 chat client with a radio process owned by the same Bash session."""
import argparse
import json
from pathlib import Path
import secrets
import signal
import sqlite3
import sys
import time
import uuid
import zmq
from PyQt5 import QtCore, QtGui, QtWidgets as W
from .config import load,addr
from .identity import contact_code,contact_card,parse_contact,accept_invitation,make_invitation

PRIORITIES=['High','Normal','Low']
THEMES={
    'midnight':dict(name='Midnight',dark=True,bg='#111927',side='#1B293C',card='#24354B',text='#EDF3FC',muted='#9AADC5',sent='#304E7D',received='#26364D',border='#374961',accent='#7DA9FF'),
    'daylight':dict(name='Daylight',dark=False,bg='#EAF0F8',side='#FFFFFF',card='#F0F4FA',text='#24364F',muted='#6C7E97',sent='#DAE8FF',received='#FFFFFF',border='#D7E1EF',accent='#447FE5'),
    'dusk':dict(name='Dusk',dark=True,bg='#211B30',side='#30273F',card='#3D3150',text='#F5EDFC',muted='#B6A3CB',sent='#60477D',received='#382D4A',border='#514262',accent='#C29AF0'),
    'lagoon':dict(name='Lagoon',dark=True,bg='#102728',side='#193738',card='#244649',text='#E5F6F3',muted='#99BCB9',sent='#286466',received='#234244',border='#34585A',accent='#6CD3C6'),
}


class TitleBar(W.QFrame):
    """Native window movement, with a fallback for platforms without startSystemMove."""
    def __init__(self,window):
        super().__init__(window);self.window=window;self.origin=None;self.setObjectName('titleBar');self.setFixedHeight(44)
        layout=W.QHBoxLayout(self);layout.setContentsMargins(18,0,8,0);layout.setSpacing(5)
        title=W.QLabel('◈  Pixel Pulse');title.setObjectName('windowBrand');title.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents);layout.addWidget(title,1)
        for text,tip,callback in [('−','Minimize',window.showMinimized),('□','Maximize / restore',self.toggle_maximized),('×','Close',window.close)]:
            button=W.QPushButton(text);button.setObjectName('closeWindow' if text=='×' else 'windowControl');button.setFixedSize(32,28);button.setToolTip(tip);button.clicked.connect(callback);layout.addWidget(button)

    def toggle_maximized(self):
        self.window.showNormal() if self.window.isMaximized() else self.window.showMaximized()

    def mousePressEvent(self,event):
        if event.button()==QtCore.Qt.LeftButton:
            handle=self.window.windowHandle()
            if handle and hasattr(handle,'startSystemMove') and handle.startSystemMove():return
            self.origin=event.globalPos()-self.window.frameGeometry().topLeft();event.accept()

    def mouseMoveEvent(self,event):
        if self.origin is not None and event.buttons()&QtCore.Qt.LeftButton and not self.window.isMaximized():
            self.window.move(event.globalPos()-self.origin);event.accept()

    def mouseReleaseEvent(self,event):
        self.origin=None

    def mouseDoubleClickEvent(self,event):
        if event.button()==QtCore.Qt.LeftButton:self.toggle_maximized()



def avatar(name,address,size):
    pixmap=QtGui.QPixmap(size,size);pixmap.fill(QtCore.Qt.transparent)
    painter=QtGui.QPainter(pixmap);painter.setRenderHint(QtGui.QPainter.Antialiasing)
    colors=['#568AB5','#7985BE','#5A9C98','#B78A65','#9880B5']
    painter.setBrush(QtGui.QColor(colors[address%len(colors)]));painter.setPen(QtCore.Qt.NoPen);painter.drawEllipse(0,0,size,size)
    painter.setPen(QtGui.QColor('white'));font=QtGui.QFont('DejaVu Sans',int(size*.25));font.setBold(True);painter.setFont(font)
    initials=''.join(part[0] for part in name.split()[:2]).upper() or '?'
    painter.drawText(pixmap.rect(),QtCore.Qt.AlignCenter,'#' if address==65535 else initials);painter.end();return pixmap


class SmoothScrollBar(W.QScrollBar):
    def __init__(self,parent=None):
        super().__init__(QtCore.Qt.Vertical,parent);self.animation=QtCore.QPropertyAnimation(self,b'value',self);self.animation.setEasingCurve(QtCore.QEasingCurve.OutCubic);self.animation.setDuration(150)
        self.target=0

    def wheelEvent(self,event):
        if not event.pixelDelta().isNull():
            self.animation.stop();self.setValue(self.value()-event.pixelDelta().y());event.accept();return
        start=self.target if self.animation.state()==QtCore.QAbstractAnimation.Running else self.value()
        self.target=max(self.minimum(),min(self.maximum(),start-round(event.angleDelta().y()/120*90)))
        self.animation.stop();self.animation.setStartValue(self.value());self.animation.setEndValue(self.target);self.animation.start();event.accept()


class ContactDelegate(W.QStyledItemDelegate):
    def __init__(self,window):
        super().__init__(window);self.window=window

    def sizeHint(self,option,index):
        return QtCore.QSize(280,82)

    def paint(self,painter,option,index):
        painter.save();painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect=option.rect.adjusted(0,2,0,-2);dark=getattr(self.window,'dark',True)
        selected=bool(option.state&W.QStyle.State_Selected)
        if selected or option.state&W.QStyle.State_MouseOver:
            painter.setPen(QtCore.Qt.NoPen);painter.setBrush(QtGui.QColor(self.window.colors['sent'] if selected else self.window.colors['card']));painter.drawRoundedRect(rect,18,18)
        name,preview,stamp=index.data(QtCore.Qt.UserRole+1);address=index.data(QtCore.Qt.UserRole)
        painter.drawPixmap(rect.x()+10,rect.y()+15,avatar(name,address,46))
        x=rect.x()+68;width=rect.width()-80
        font=QtGui.QFont('DejaVu Sans',10);font.setBold(True);painter.setFont(font);painter.setPen(QtGui.QColor(self.window.colors['text']))
        painter.drawText(QtCore.QRect(x,rect.y()+16,width-42,22),QtCore.Qt.AlignLeft,painter.fontMetrics().elidedText(name,QtCore.Qt.ElideRight,width-42))
        font.setBold(False);font.setPointSize(8);painter.setFont(font);painter.setPen(QtGui.QColor(self.window.colors['muted']))
        if stamp:painter.drawText(QtCore.QRect(x,rect.y()+18,width,18),QtCore.Qt.AlignRight,time.strftime('%H:%M',time.localtime(stamp)))
        unread,pinned=index.data(QtCore.Qt.UserRole+2) or (0,False)
        badge_width=max(22,painter.fontMetrics().horizontalAdvance(str(unread))+14) if unread else 0
        reserved=(badge_width+8 if unread else 0)+(20 if pinned else 0)
        painter.drawText(QtCore.QRect(x,rect.y()+43,width-reserved,20),QtCore.Qt.AlignLeft,painter.fontMetrics().elidedText(preview,QtCore.Qt.ElideRight,max(0,width-reserved)))
        if pinned:
            painter.save();painter.translate(rect.right()-12-badge_width-(8 if unread else 0),rect.y()+52);painter.rotate(35)
            painter.setPen(QtGui.QPen(QtGui.QColor(self.window.colors['muted']),1.5))
            painter.drawLine(-4,-5,4,-5);painter.drawLine(-2,-5,-2,1);painter.drawLine(2,-5,2,1)
            painter.drawLine(-5,2,5,2);painter.drawLine(0,2,0,8);painter.restore()
        if unread:
            badge=QtCore.QRectF(rect.right()-10-badge_width,rect.y()+42,badge_width,22)
            painter.setPen(QtCore.Qt.NoPen);painter.setBrush(QtGui.QColor('#E65060'));painter.drawRoundedRect(badge,11,11)
            painter.setPen(QtGui.QColor('white'));font.setBold(True);painter.setFont(font)
            painter.drawText(badge,QtCore.Qt.AlignCenter,str(unread))
        painter.restore()


class Database:
    def __init__(self,c):
        self.c=c;self.db=sqlite3.connect(str(Path(c['state_dir'])/'chat.sqlite'))
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS contacts(address INTEGER PRIMARY KEY,name TEXT NOT NULL,priority INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS messages(id TEXT,contact INTEGER,outgoing INTEGER,kind TEXT,body TEXT,path TEXT,status TEXT,stamp REAL,command TEXT,detail TEXT DEFAULT '',PRIMARY KEY(id,contact,outgoing));
        CREATE TABLE IF NOT EXISTS preferences(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS chat_state(address INTEGER PRIMARY KEY,pinned INTEGER NOT NULL DEFAULT 0,unread INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS address_reservations(address INTEGER PRIMARY KEY);
        CREATE INDEX IF NOT EXISTS messages_contact_stamp ON messages(contact,stamp);
        ''')
        self.db.execute('INSERT OR IGNORE INTO contacts VALUES(65535,?,1)',('Everyone',))
        if not self.db.execute("SELECT 1 FROM preferences WHERE key='contacts_seeded'").fetchone():
            for person in c.get('contacts',[]):
                if person['address']!=c['address']:self.db.execute('INSERT OR IGNORE INTO contacts VALUES(?,?,?)',(person['address'],person['name'],person.get('priority',1)))
            self.db.execute("INSERT INTO preferences VALUES('contacts_seeded','1')")
        self.db.execute('INSERT OR IGNORE INTO address_reservations SELECT address FROM contacts')
        self.db.execute('INSERT OR IGNORE INTO address_reservations SELECT DISTINCT contact FROM messages')
        self.db.commit()

    def ordered_contacts(self):
        return self.db.execute('''
            SELECT c.address,c.name,c.priority,COALESCE(s.unread,0),COALESCE(s.pinned,0)
            FROM contacts c LEFT JOIN chat_state s ON s.address=c.address
            LEFT JOIN (SELECT contact,MAX(stamp) AS latest FROM messages GROUP BY contact) m ON m.contact=c.address
            ORDER BY COALESCE(s.pinned,0) DESC,COALESCE(m.latest,0) DESC,c.name COLLATE NOCASE,c.address
        ''').fetchall()

    def mark_read(self,address):
        cursor=self.db.execute('UPDATE chat_state SET unread=0 WHERE address=? AND unread>0',(address,))
        self.db.commit();return bool(cursor.rowcount)

    def toggle_pin(self,address):
        self.db.execute('''INSERT INTO chat_state(address,pinned) VALUES(?,1)
            ON CONFLICT(address) DO UPDATE SET pinned=1-pinned''',(address,))
        self.db.commit()

    def receive(self,event,read=False):
        src=event['src']
        self.db.execute('INSERT OR IGNORE INTO address_reservations VALUES(?)',(src,))
        self.db.execute('INSERT OR IGNORE INTO contacts VALUES(?,?,1)',(src,'New contact'))
        cursor=self.db.execute('INSERT OR IGNORE INTO messages VALUES(?,?,?,?,?,?,?,?,?,?)',
            (event['id'],src,0,event['kind'],event.get('text',event.get('name','')),event.get('path',''),'received',time.time(),'',''))
        if cursor.rowcount and not read:
            self.db.execute('''INSERT INTO chat_state(address,unread) VALUES(?,1)
                ON CONFLICT(address) DO UPDATE SET unread=unread+1''',(src,))
        self.db.commit();return bool(cursor.rowcount)

    def allocate(self):
        used={r[0] for r in self.db.execute('SELECT address FROM contacts UNION SELECT address FROM address_reservations')}|{self.c['address'],0,65535}
        if len(used)>=65536:raise ValueError('All 16-bit addresses are allocated')
        while True:
            candidate=secrets.randbelow(65534)+1
            if candidate not in used:return candidate


class ContactDialog(W.QDialog):
    def __init__(self,book,contact=None,parent=None):
        super().__init__(parent);self.book=book;self.contact=contact
        self.setWindowTitle('Edit contact' if contact else 'Add contact');self.setMinimumWidth(420)
        layout=W.QFormLayout(self)
        self.name=W.QLineEdit(contact[1] if contact else '')
        self.mode=W.QComboBox();self.mode.addItems(['Existing node — enter its address','New node — allocate an address'])
        self.address=W.QLineEdit(addr(contact[0]) if contact else '')
        self.address.setPlaceholderText('e.g. 0x4B2B')
        self.address.setReadOnly(contact is not None);self.mode.currentIndexChanged.connect(self.address_mode)
        self.priority=W.QComboBox();self.priority.addItems(PRIORITIES);self.priority.setCurrentIndex(contact[2] if contact else 1)
        layout.addRow('Name',self.name)
        self.code=W.QLineEdit();self.code.setPlaceholderText('Paste their PP1: contact code')
        if not contact:layout.addRow('Contact code (optional)',self.code)
        self.code.textChanged.connect(self.apply_code)
        if not contact:layout.addRow('Address assignment',self.mode)
        layout.addRow('Node address',self.address);layout.addRow('Message priority',self.priority)
        note=W.QLabel('For an existing person, paste the code from their Details tab or enter their address. To invite someone new, allocate an address and export their invitation. Use one coordinator for address allocation.');note.setWordWrap(True)
        layout.addRow(note)
        buttons=W.QDialogButtonBox(W.QDialogButtonBox.Save|W.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);layout.addRow(buttons)

    def address_mode(self,index):
        self.address.setReadOnly(index==1)
        self.address.setText(addr(self.book.allocate()) if index==1 else '')

    def apply_code(self,text):
        if not text.strip():return
        try:person=parse_contact(text,self.book.c)
        except ValueError:return
        self.mode.setCurrentIndex(0);self.name.setText(person['name']);self.address.setText(addr(person['address']))

    def save(self):
        try:
            if self.code.text().strip():
                person=parse_contact(self.code.text(),self.book.c)
                if int(self.address.text(),16)!=person['address']:raise ValueError('The address must match the pasted contact code')
            value=int(self.address.text(),16)
            if not self.name.text().strip():raise ValueError('Enter a contact name')
            if value==self.book.c['address'] or not 1<=value<=65534:raise ValueError('Use a unique address from 0x0001 to 0xFFFE')
            if not self.contact and self.book.db.execute('SELECT 1 FROM contacts WHERE address=?',(value,)).fetchone():raise ValueError('That address already exists. If this is a different person, ask the coordinator for a new invitation.')
            if self.contact:self.book.db.execute('UPDATE contacts SET name=?,priority=? WHERE address=?',(self.name.text().strip(),self.priority.currentIndex(),value))
            else:self.book.db.execute('INSERT INTO contacts VALUES(?,?,?)',(value,self.name.text().strip(),self.priority.currentIndex()))
            self.book.db.execute('INSERT OR IGNORE INTO address_reservations VALUES(?)',(value,))
            self.book.db.commit();self.accept()
        except (ValueError,sqlite3.Error) as exc:W.QMessageBox.warning(self,'Contact',str(exc))


class WelcomeDialog(W.QDialog):
    def __init__(self,destination):
        super().__init__();self.destination=destination;self.setWindowTitle('Pixel Pulse · Welcome');self.setMinimumWidth(470)
        layout=W.QFormLayout(self);layout.setContentsMargins(26,26,26,26);layout.setSpacing(16)
        title=W.QLabel('Welcome to Pixel Pulse');title.setStyleSheet('font-size:22px;font-weight:600');layout.addRow(title)
        note=W.QLabel('Ask the network coordinator for an invitation issued just for you. It assigns your radio address and adds the coordinator as a contact. Do not reuse someone else’s invitation or profile.');note.setWordWrap(True);layout.addRow(note)
        self.name=W.QLineEdit();self.name.setPlaceholderText('Your display name');layout.addRow('Your name',self.name)
        self.invitation=W.QLineEdit();self.invitation.setReadOnly(True);self.invitation.setPlaceholderText('Choose your invitation JSON')
        row=W.QHBoxLayout();row.addWidget(self.invitation,1);browse=W.QPushButton('Browse…');browse.clicked.connect(self.browse);row.addWidget(browse);layout.addRow('Invitation',row)
        buttons=W.QDialogButtonBox(W.QDialogButtonBox.Ok|W.QDialogButtonBox.Cancel);buttons.button(W.QDialogButtonBox.Ok).setText('Create my profile');buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);layout.addRow(buttons)

    def browse(self):
        path,_=W.QFileDialog.getOpenFileName(self,'Select your personal invitation','','JSON (*.json)')
        if path:self.invitation.setText(path)

    def save(self):
        try:
            if not self.invitation.text():raise ValueError('Choose the invitation issued for you')
            accept_invitation(self.invitation.text(),self.name.text(),self.destination);self.accept()
        except (OSError,ValueError,KeyError,TypeError) as exc:W.QMessageBox.warning(self,'Profile setup',str(exc))


class Composer(W.QPlainTextEdit):
    send=QtCore.pyqtSignal()
    def keyPressEvent(self,event):
        if event.key() in (QtCore.Qt.Key_Return,QtCore.Qt.Key_Enter) and not event.modifiers()&QtCore.Qt.ShiftModifier:self.send.emit()
        else:super().keyPressEvent(event)


class AttachmentWorker(QtCore.QThread):
    prepared=QtCore.pyqtSignal(object)
    def __init__(self,path,kind,state_dir,contact):
        super().__init__();self.path=path;self.kind=kind;self.state_dir=state_dir;self.contact=contact
    def run(self):
        try:
            from .media import MediaEncoder
            source=Path(self.path);data=source.read_bytes();name=source.name
            if self.kind in ('image','audio'):
                encoder=MediaEncoder()
                try:data,name=getattr(encoder,'_encode_'+self.kind)(source,data)
                except Exception:pass # Preserve original file if optional codec is unavailable.
            folder=Path(self.state_dir)/'outgoing';folder.mkdir(exist_ok=True)
            target=folder/(uuid.uuid4().hex+'_'+name);target.write_bytes(data)
            self.prepared.emit(dict(kind=self.kind,name=name,path=str(target),contact=self.contact))
        except Exception as exc:self.prepared.emit(dict(error=str(exc)))


class Window(W.QMainWindow):
    def __init__(self,c):
        super().__init__();self.c=c;self.book=Database(c);self.db=self.book.db;self.selected=None
        self.setWindowTitle('Pixel Pulse');self.resize(1160,820)
        self.setWindowFlags(self.windowFlags()|QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setWindowIcon(QtGui.QIcon(avatar('Pixel Pulse',1,64)))
        saved=self.db.execute("SELECT value FROM preferences WHERE key='theme'").fetchone()
        key={'dark':'midnight','light':'daylight'}.get(saved[0],saved[0]) if saved else 'midnight'
        self.theme_name=key if key in THEMES else 'midnight';self.colors=THEMES[self.theme_name];self.dark=self.colors['dark']
        saved=self.db.execute("SELECT value FROM preferences WHERE key='transparency'").fetchone()
        try:self.surface_opacity=max(75,min(100,int(saved[0]))) if saved else 96
        except ValueError:self.surface_opacity=96
        self.scroll_animation=None;self.fade_animation=None;self.theme_animation=None;self.theme_overlay=None
        self.setMinimumSize(820,560);self.last_event=0;self.last_hello=0;self.last_resend=0
        self.ctx=zmq.Context();self.tx=self.ctx.socket(zmq.PUSH);self.rx=self.ctx.socket(zmq.PULL)
        for s in (self.tx,self.rx):s.setsockopt(zmq.LINGER,0)
        self.tx.setsockopt(zmq.IMMEDIATE,1);self.tx.setsockopt(zmq.SNDHWM,100)
        self.tx.connect(f"tcp://127.0.0.1:{c['commands_port']}");self.rx.connect(f"tcp://127.0.0.1:{c['events_port']}")
        self.build();self.refresh_contacts()
        self.theme()
        self.workers=[];self.timer=QtCore.QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(50)

    def build(self):
        central=W.QWidget();central.setObjectName('desktop');self.setCentralWidget(central)
        outside=W.QVBoxLayout(central);outside.setContentsMargins(10,10,10,10)
        self.shell=W.QFrame();self.shell.setObjectName('shell');outside.addWidget(self.shell)
        shadow=W.QGraphicsDropShadowEffect(self.shell);shadow.setBlurRadius(22);shadow.setOffset(0,4);shadow.setColor(QtGui.QColor(0,0,0,65));self.shell.setGraphicsEffect(shadow)
        shell_layout=W.QVBoxLayout(self.shell);shell_layout.setContentsMargins(8,0,8,8);shell_layout.setSpacing(0)
        self.title_bar=TitleBar(self);shell_layout.addWidget(self.title_bar)
        body=W.QWidget();root=W.QHBoxLayout(body);root.setContentsMargins(0,0,0,0);root.setSpacing(10);shell_layout.addWidget(body,1)
        sidebar=W.QFrame();sidebar.setObjectName('sidebar');sidebar.setFixedWidth(320);left=W.QVBoxLayout(sidebar)
        left.setContentsMargins(16,24,16,18);left.setSpacing(14)
        brand=W.QHBoxLayout();title=W.QLabel('Pixel Pulse');title.setObjectName('brand');brand.addWidget(title,1)
        menu_button=W.QPushButton('☰');menu_button.setObjectName('iconButton');menu_button.setFixedSize(38,38);menu_button.setToolTip('Application settings')
        menu=W.QMenu(menu_button)
        for label,callback in [('Invite someone…',self.invite_contact),('Import contact',self.import_contact),('Appearance…',self.show_appearance),('Details',self.show_radio_details)]:
            menu.addAction(label,callback)
        menu_button.setMenu(menu);brand.addWidget(menu_button);left.addLayout(brand)
        ident=W.QLabel(self.c['name']);ident.setObjectName('muted');left.addWidget(ident)
        self.search=W.QLineEdit();self.search.setPlaceholderText('Search contacts');self.search.setClearButtonEnabled(True);self.search.textChanged.connect(self.refresh_contacts);left.addWidget(self.search)
        section=W.QHBoxLayout();caption=W.QLabel('MESSAGES');caption.setObjectName('section');section.addWidget(caption,1)
        add=W.QPushButton('+ New contact');add.setObjectName('textButton');add.clicked.connect(self.add_contact);section.addWidget(add);left.addLayout(section)
        self.contacts=W.QListWidget();self.contacts.setItemDelegate(ContactDelegate(self));self.contacts.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.contacts.currentItemChanged.connect(self.select_contact);left.addWidget(self.contacts,1)
        self.contacts.setContextMenuPolicy(QtCore.Qt.CustomContextMenu);self.contacts.customContextMenuRequested.connect(self.chat_context_menu)
        self.no_contacts=W.QLabel('No matching contacts');self.no_contacts.setObjectName('muted');self.no_contacts.setAlignment(QtCore.Qt.AlignCenter);left.addWidget(self.no_contacts);self.no_contacts.hide()
        self.connection=W.QLabel('Connecting to radio…');self.connection.setObjectName('muted');self.connection.setWordWrap(True)
        appearance=W.QPushButton('◐  Appearance');appearance.setObjectName('appearanceButton');appearance.clicked.connect(self.show_appearance);left.addWidget(appearance)
        local=W.QLabel('Your conversations, saved on this device');local.setObjectName('muted');left.addWidget(local)
        root.addWidget(sidebar)
        panel=W.QWidget();panel.setObjectName('chatPanel');right=W.QVBoxLayout(panel);right.setContentsMargins(0,0,0,0);right.setSpacing(8)
        header=W.QFrame();header.setObjectName('header');head=W.QHBoxLayout(header);head.setContentsMargins(26,20,24,20)
        self.chat_avatar=W.QLabel();self.chat_avatar.setFixedSize(44,44);head.addWidget(self.chat_avatar);head.addSpacing(8)
        names=W.QVBoxLayout();names.setSpacing(5);self.chat_title=W.QLabel('Your conversations');self.chat_title.setObjectName('chatTitle')
        self.subtitle=W.QLabel('Choose a contact to start chatting');self.subtitle.setObjectName('muted')
        names.addWidget(self.chat_title);head.addLayout(names,1)
        self.queue_label=W.QLabel('0 messages waiting');self.queue_label.setObjectName('queue')
        self.contact_menu=W.QPushButton('•••');self.contact_menu.setObjectName('iconButton');self.contact_menu.setFixedSize(40,40);self.contact_menu.setToolTip('Contact options')
        options=W.QMenu(self.contact_menu)
        self.pin_action=options.addAction('Pin chat',self.toggle_pin)
        options.addSeparator()
        self.edit_action=options.addAction('Edit contact',self.edit_contact)
        self.export_action=options.addAction('Export invitation',self.export_setup)
        options.addSeparator();self.delete_action=options.addAction('Delete contact',self.delete_contact)
        self.contact_menu.setMenu(options);head.addWidget(self.contact_menu);right.addWidget(header)
        self.details_tabs=W.QTabWidget();self.details_tabs.setObjectName('conversationTabs');right.addWidget(self.details_tabs,1)
        chat_page=W.QWidget();chat_layout=W.QVBoxLayout(chat_page);chat_layout.setContentsMargins(0,8,0,0);chat_layout.setSpacing(8)
        self.details_tabs.addTab(chat_page,'Chat')
        self.scroll=W.QScrollArea();self.scroll.setWidgetResizable(True);self.scroll.setObjectName('conversation')
        self.history_body=W.QWidget();self.history=W.QVBoxLayout(self.history_body);self.history.setContentsMargins(32,24,32,24);self.history.setSpacing(10);self.history.addStretch()
        self.scroll.setWidget(self.history_body);self.scroll.setVerticalScrollBar(SmoothScrollBar(self.scroll));chat_layout.addWidget(self.scroll,1)
        self.notice=W.QLabel('Enter to send  ·  Shift+Enter for a new line');self.notice.setObjectName('muted');self.notice.setWordWrap(True);self.notice.setContentsMargins(28,8,28,12);chat_layout.addWidget(self.notice)
        composer=W.QFrame();composer.setObjectName('header');bottom=W.QHBoxLayout(composer);bottom.setContentsMargins(24,16,24,16);bottom.setSpacing(12)
        attach=W.QPushButton('+');attach.setObjectName('iconButton');attach.setFixedSize(42,42);attach.setToolTip('Attach a photo, audio, or file');attach.clicked.connect(self.attach_file);bottom.addWidget(attach)
        self.composer=Composer();self.composer.setPlaceholderText('Write a message…');self.composer.setFixedHeight(64);self.composer.send.connect(self.send_text);bottom.addWidget(self.composer,1)
        self.send_button=W.QPushButton('Send ↗');self.send_button.setObjectName('send');self.send_button.setFixedSize(92,44);self.send_button.clicked.connect(self.send_text);bottom.addWidget(self.send_button);chat_layout.addWidget(composer)
        self.composer.textChanged.connect(lambda:self.send_button.setEnabled(bool(self.composer.toPlainText().strip())))
        self.send_button.setEnabled(False)
        # Technical information is visible only after opening the Details tab.
        details_page=W.QWidget();details_layout=W.QVBoxLayout(details_page);details_layout.setContentsMargins(24,24,24,24)
        settings=W.QFormLayout();settings.setSpacing(18);details_layout.addLayout(settings);details_layout.addStretch()
        self.detail_name=W.QLabel();self.detail_address=W.QLabel()
        settings.addRow('Contact',self.detail_name);settings.addRow('Contact address',self.detail_address)
        settings.addRow('Conversation',self.subtitle)
        settings.addRow('Your name',W.QLabel(self.c['name']))
        settings.addRow('Your address',W.QLabel(addr(self.c['address'])))
        my_code=W.QLineEdit(contact_code(self.c));my_code.setReadOnly(True);my_code.setCursorPosition(0)
        settings.addRow('Your contact code',my_code)
        share=W.QHBoxLayout();copy=W.QPushButton('Copy my contact code');copy.clicked.connect(lambda:W.QApplication.clipboard().setText(contact_code(self.c)));share.addWidget(copy)
        save_card=W.QPushButton('Save contact card');save_card.clicked.connect(self.save_contact_card);share.addWidget(save_card);settings.addRow(share)
        settings.addRow('Radio',self.connection);settings.addRow('Outbox',self.queue_label)
        settings.addRow('Frequency',W.QLabel(f"{self.c['frequency']/1e9:g} GHz"))
        self.channel=W.QLabel('Waiting for radio');self.channel.setWordWrap(True);settings.addRow('Channel',self.channel)
        self.threshold=W.QDoubleSpinBox();self.threshold.setRange(-140,20);self.threshold.setValue(self.c['cs_threshold_db']);self.threshold.setSuffix(' dB')
        self.threshold.valueChanged.connect(lambda v:self.command(dict(cmd='threshold',db=v)));settings.addRow('Sense threshold',self.threshold)
        self.priority=W.QComboBox();self.priority.addItems(PRIORITIES);self.priority.currentIndexChanged.connect(self.change_priority);settings.addRow('Selected contact priority',self.priority)
        self.details_note=W.QLabel('The radio starts with this app and stops when you close it. Messages wait in the outbox while it is offline.');self.details_note.setWordWrap(True);settings.addRow(self.details_note)
        details_scroll=W.QScrollArea();details_scroll.setWidgetResizable(True);details_scroll.setWidget(details_page)
        self.details_tabs.addTab(details_scroll,'Details');self.details_tabs.currentChanged.connect(lambda _:self.mark_selected_read())
        root.addWidget(panel,1)
        self.resize_grip=W.QSizeGrip(self.shell);self.resize_grip.setFixedSize(14,14);shell_layout.addWidget(self.resize_grip,0,QtCore.Qt.AlignRight)
        self.build_appearance()

    def show_radio_details(self):
        self.details_tabs.setCurrentIndex(1)

    def build_appearance(self):
        self.appearance_dialog=W.QDialog(self);self.appearance_dialog.setWindowTitle('Pixel Pulse · Appearance');self.appearance_dialog.setMinimumWidth(430)
        layout=W.QVBoxLayout(self.appearance_dialog);layout.setContentsMargins(26,26,26,26);layout.setSpacing(18)
        title=W.QLabel('Make it yours');title.setObjectName('chatTitle');layout.addWidget(title)
        note=W.QLabel('Choose your mood. Your preferences are saved automatically.');note.setWordWrap(True);note.setObjectName('muted');layout.addWidget(note)
        choices=W.QGridLayout();self.theme_buttons={};self.theme_group=W.QButtonGroup(self.appearance_dialog);self.theme_group.setExclusive(True)
        for i,(key,palette) in enumerate(THEMES.items()):
            button=W.QPushButton('●  '+palette['name']);button.setCheckable(True);button.setMinimumHeight(58);self.theme_group.addButton(button);self.theme_buttons[key]=button
            button.setChecked(key==self.theme_name);button.clicked.connect(lambda checked,k=key:self.set_theme(k));choices.addWidget(button,i//2,i%2)
        layout.addLayout(choices)
        row=W.QHBoxLayout();row.addWidget(W.QLabel('Window opacity'),1);self.opacity_label=W.QLabel(f'{self.surface_opacity}%');row.addWidget(self.opacity_label);layout.addLayout(row)
        self.opacity_slider=W.QSlider(QtCore.Qt.Horizontal);self.opacity_slider.setRange(75,100);self.opacity_slider.setValue(self.surface_opacity);self.opacity_slider.valueChanged.connect(self.set_surface_opacity);layout.addWidget(self.opacity_slider)
        hint=W.QLabel('Lower opacity lets your desktop show through the window. Text stays crisp.');hint.setObjectName('muted');hint.setWordWrap(True);layout.addWidget(hint)
        done=W.QDialogButtonBox(W.QDialogButtonBox.Close);done.rejected.connect(self.appearance_dialog.hide);layout.addWidget(done)

    def show_appearance(self):
        self.appearance_dialog.show();self.appearance_dialog.raise_();self.appearance_dialog.activateWindow()

    def set_surface_opacity(self,value):
        self.surface_opacity=max(75,min(100,value));self.opacity_label.setText(f'{self.surface_opacity}%')
        self.db.execute('INSERT OR REPLACE INTO preferences VALUES(?,?)',('transparency',str(self.surface_opacity)));self.db.commit();self.theme()

    def set_theme(self,key,animate=True):
        if key not in THEMES:return
        if self.theme_animation:self.theme_animation.stop()
        if self.theme_overlay:self.theme_overlay.hide();self.theme_overlay.deleteLater();self.theme_overlay=None
        if animate and self.isVisible():
            snapshot=self.shell.grab();self.theme_overlay=W.QLabel(self.shell);self.theme_overlay.setPixmap(snapshot);self.theme_overlay.setGeometry(self.shell.rect());self.theme_overlay.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.theme_name=key;self.colors=THEMES[key];self.dark=self.colors['dark'];self.theme()
        self.db.execute('INSERT OR REPLACE INTO preferences VALUES(?,?)',('theme',key));self.db.commit()
        if self.theme_overlay:
            overlay=self.theme_overlay;overlay.show();overlay.raise_();effect=W.QGraphicsOpacityEffect(overlay);overlay.setGraphicsEffect(effect)
            self.theme_animation=QtCore.QPropertyAnimation(effect,b'opacity',self);self.theme_animation.setDuration(220);self.theme_animation.setStartValue(1.0);self.theme_animation.setEndValue(0.0);self.theme_animation.setEasingCurve(QtCore.QEasingCurve.OutCubic)
            self.theme_animation.finished.connect(overlay.hide);self.theme_animation.start()

    def theme(self):
        c=self.colors;bg,side,card,text,muted,sent,received,border,accent=(c[k] for k in ('bg','side','card','text','muted','sent','received','border','accent'))
        base=QtGui.QColor(bg);tint=QtGui.QColor(side);alpha=round(self.surface_opacity*2.55)
        glass=f'rgba({base.red()},{base.green()},{base.blue()},{alpha})';glow=f'rgba({tint.red()},{tint.green()},{tint.blue()},{alpha})'
        panel=f'rgba({tint.red()},{tint.green()},{tint.blue()},175)'
        self.setStyleSheet(f'''
        QWidget {{background:transparent;color:{text};font-family:DejaVu Sans;font-size:13px;}}
        QMainWindow,QWidget#desktop {{background:transparent;}}
        QFrame#shell {{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {glow},stop:0.45 {glass},stop:1 {glow});border:1px solid {border};border-radius:24px;}}
        QFrame#sidebar {{background:{panel};border:1px solid {border};border-radius:20px;}}
        QFrame#header {{background:{panel};border:1px solid {border};border-radius:20px;}}
        QDialog {{background:{bg};}}
        QLabel {{background:transparent;border:0;}}
        QLabel#windowBrand {{font-size:11px;font-weight:600;color:{muted};}}
        QLabel#brand {{font-size:24px;font-weight:700;}}
        QLabel#chatTitle {{font-size:18px;font-weight:600;}}
        QLabel#muted {{color:{muted};font-size:11px;}}
        QLabel#section {{color:{muted};font-size:10px;font-weight:600;letter-spacing:1px;}}
        QLabel#queue {{background:{card};color:{muted};border-radius:12px;padding:8px 12px;font-size:10px;}}
        QLabel#date {{color:{muted};font-size:10px;padding:12px;}}
        QListWidget {{background:transparent;border:0;outline:0;}}
        QLineEdit,QPlainTextEdit,QComboBox,QDoubleSpinBox {{background:{card};border:1px solid {border};border-radius:14px;padding:10px;selection-background-color:{accent};}}
        QLineEdit:focus,QPlainTextEdit:focus {{border:1px solid {accent};}}
        QPushButton {{background:{card};border:1px solid transparent;border-radius:14px;padding:10px;}}
        QPushButton:hover {{background:{sent};border:1px solid {border};}}
        QPushButton:checked {{background:{sent};border:1px solid {accent};}}
        QPushButton#textButton {{color:{accent};background:transparent;padding:6px;font-size:11px;}}
        QPushButton#iconButton {{background:transparent;color:{muted};font-size:20px;padding:0;}}
        QPushButton#iconButton:hover {{background:{card};}}
        QPushButton#appearanceButton {{color:{accent};text-align:left;}}
        QPushButton#windowControl,QPushButton#closeWindow {{background:transparent;color:{muted};font-size:17px;padding:0;border-radius:8px;}}
        QPushButton#windowControl:hover {{background:{card};}}
        QPushButton#closeWindow:hover {{background:#D94B64;color:white;}}
        QPushButton::menu-indicator {{image:none;}}
        QPushButton#send {{background:{accent};color:{bg};font-weight:600;border-radius:18px;}}
        QPushButton#send:hover {{background:{text};}}
        QPushButton#send:disabled {{background:{card};color:{muted};}}
        QMenu {{background:{side};border:1px solid {border};padding:6px;border-radius:12px;}}
        QMenu::item {{padding:10px 24px;border-radius:7px;}}
        QMenu::item:selected {{background:{sent};}}
        QMenu::item:disabled {{color:{muted};}}
        QFrame#sentBubble {{background:{sent};border-radius:18px;}}
        QFrame#receivedBubble {{background:{received};border-radius:18px;}}
        QScrollArea {{border:0;}}
        QScrollBar:vertical {{background:transparent;width:6px;}}
        QScrollBar::handle:vertical {{background:{border};border-radius:3px;min-height:24px;}}
        QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}}
        QSlider::groove:horizontal {{background:{border};height:5px;border-radius:2px;}}
        QSlider::sub-page:horizontal {{background:{accent};border-radius:2px;}}
        QSlider::handle:horizontal {{background:{accent};border:2px solid {side};width:16px;height:16px;margin:-7px 0;border-radius:10px;}}
        QTabWidget::pane {{border:0;background:transparent;}}
        QTabBar::tab {{background:transparent;color:{muted};padding:10px 24px;margin-right:8px;border-radius:12px;}}
        QTabBar::tab:selected {{background:{sent};color:{text};}}
        QTabBar::tab:hover {{background:{card};}}
        ''')
        for key,button in self.theme_buttons.items():
            button.setChecked(key==self.theme_name)
            palette=THEMES[key]
            button.setStyleSheet(f"QPushButton {{background:{palette['side']};color:{palette['accent']};border:2px solid {palette['accent'] if key==self.theme_name else palette['border']};border-radius:14px;padding:12px;}}")
        self.contacts.viewport().update()

    def toggle_theme(self):
        self.set_theme('daylight' if self.dark else 'midnight')

    def fade_conversation(self):
        if not self.isVisible():return
        if self.fade_animation:self.fade_animation.stop()
        effect=self.history_body.graphicsEffect()
        if effect is None:effect=W.QGraphicsOpacityEffect(self.history_body);self.history_body.setGraphicsEffect(effect)
        self.fade_animation=QtCore.QPropertyAnimation(effect,b'opacity',self);self.fade_animation.setDuration(160);self.fade_animation.setStartValue(.35);self.fade_animation.setEndValue(1.0);self.fade_animation.setEasingCurve(QtCore.QEasingCurve.OutCubic);self.fade_animation.start()

    def scroll_to_latest(self):
        bar=self.scroll.verticalScrollBar()
        if self.scroll_animation:self.scroll_animation.stop()
        self.scroll_animation=QtCore.QPropertyAnimation(bar,b'value',self);self.scroll_animation.setDuration(180);self.scroll_animation.setStartValue(bar.value());self.scroll_animation.setEndValue(bar.maximum());self.scroll_animation.setEasingCurve(QtCore.QEasingCurve.OutCubic);self.scroll_animation.start()

    def refresh_contacts(self):
        previous=self.selected;self.contacts.blockSignals(True);self.contacts.clear()
        for address,name,priority,unread,pinned in self.book.ordered_contacts():
            if name.lower()==addr(address).lower():name='New contact'
            if self.search.text().lower() not in (name+' '+addr(address)).lower():continue
            last=self.db.execute('SELECT body,stamp,outgoing FROM messages WHERE contact=? ORDER BY stamp DESC LIMIT 1',(address,)).fetchone()
            preview=('You: ' if last[2] else '')+last[0].replace('\n',' ') if last else ('Message everyone' if address==65535 else 'Start a conversation')
            item=W.QListWidgetItem(name);item.setData(QtCore.Qt.UserRole,address);item.setData(QtCore.Qt.UserRole+1,(name,preview,last[1] if last else None));self.contacts.addItem(item)
            item.setData(QtCore.Qt.UserRole+2,(unread,bool(pinned)))
            item.setToolTip(name+(' · Pinned' if pinned else '')+(f' · {unread} unread' if unread else ''))
            if address==previous:self.contacts.setCurrentItem(item)
        self.contacts.blockSignals(False)
        self.no_contacts.setVisible(self.contacts.count()==0)
        if self.selected is None and self.contacts.count():self.contacts.setCurrentRow(0)
        self.update_pin_action()

    def update_pin_action(self):
        state=self.db.execute('SELECT pinned FROM chat_state WHERE address=?',(self.selected,)).fetchone()
        self.pin_action.setText('Unpin chat' if state and state[0] else 'Pin chat')
        self.pin_action.setEnabled(self.selected is not None)

    def toggle_pin(self,checked=False,address=None):
        address=self.selected if address is None else address
        if address is None:return
        self.book.toggle_pin(address);self.refresh_contacts()

    def chat_context_menu(self,position):
        item=self.contacts.itemAt(position)
        if item is None:return
        address=item.data(QtCore.Qt.UserRole);pinned=item.data(QtCore.Qt.UserRole+2)[1]
        menu=W.QMenu(self);action=menu.addAction('Unpin chat' if pinned else 'Pin chat')
        action.triggered.connect(lambda:self.toggle_pin(address=address))
        menu.exec_(self.contacts.viewport().mapToGlobal(position))

    def conversation_visible(self,address):
        return address==self.selected and self.details_tabs.currentIndex()==0 and self.isVisible() and self.isActiveWindow() and not self.isMinimized()

    def mark_selected_read(self):
        if self.conversation_visible(self.selected) and self.book.mark_read(self.selected):self.refresh_contacts()

    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type() in (QtCore.QEvent.ActivationChange,QtCore.QEvent.WindowStateChange) and hasattr(self,'contacts'):
            QtCore.QTimer.singleShot(0,self.mark_selected_read)

    def contact(self):
        return self.db.execute('SELECT address,name,priority FROM contacts WHERE address=?',(self.selected,)).fetchone()

    def select_contact(self,item,old=None):
        if item is None:return
        self.selected=item.data(QtCore.Qt.UserRole);contact=self.contact()
        self.mark_selected_read();self.update_pin_action()
        name='New contact' if contact[1].lower()==addr(contact[0]).lower() else contact[1]
        self.chat_title.setText(name);self.detail_name.setText(name);self.detail_address.setText(addr(contact[0]))
        self.subtitle.setText('Broadcast · no delivery ACK' if contact[0]==65535 else 'Encrypted SDR conversation')
        self.chat_avatar.setPixmap(avatar(contact[1],contact[0],44))
        for action in (self.edit_action,self.export_action,self.delete_action):action.setEnabled(contact[0]!=65535)
        self.priority.blockSignals(True);self.priority.setCurrentIndex(contact[2]);self.priority.blockSignals(False);self.render_history();self.fade_conversation()

    def change_priority(self,value):
        if self.selected is None:return
        self.db.execute('UPDATE contacts SET priority=? WHERE address=?',(value,self.selected));self.db.commit();self.refresh_contacts()
        self.details_note.setText('Priority applies to new messages. Messages already queued keep their original priority.')

    def add_contact(self):
        dialog=ContactDialog(self.book,parent=self)
        if dialog.exec_():
            self.selected=int(dialog.address.text(),16);self.search.clear();self.refresh_contacts();self.select_contact(self.contacts.currentItem())

    def invite_contact(self):
        dialog=ContactDialog(self.book,parent=self);dialog.setWindowTitle('Invite someone');dialog.mode.setCurrentIndex(1)
        if dialog.exec_():
            self.selected=int(dialog.address.text(),16);self.search.clear();self.refresh_contacts();self.select_contact(self.contacts.currentItem());self.export_setup()

    def save_contact_card(self):
        path,_=W.QFileDialog.getSaveFileName(self,'Save your contact card','Pixel_Pulse_contact.json','JSON (*.json)')
        if not path:return
        try:Path(path).write_text(json.dumps(contact_card(self.c),indent=2)+'\n')
        except OSError as exc:W.QMessageBox.warning(self,'Contact card',str(exc))

    def edit_contact(self):
        contact=self.contact()
        if contact and contact[0]!=65535 and ContactDialog(self.book,contact,self).exec_():self.refresh_contacts();self.select_contact(self.contacts.currentItem())

    def delete_contact(self):
        if self.selected in (None,65535):return
        if W.QMessageBox.question(self,'Delete contact','Remove this contact? Saved history remains available if you add the same address again.')==W.QMessageBox.Yes:
            self.db.execute('DELETE FROM contacts WHERE address=?',(self.selected,));self.db.execute('DELETE FROM chat_state WHERE address=?',(self.selected,));self.db.commit();self.selected=None;self.search.clear();self.refresh_contacts()

    def export_setup(self):
        contact=self.contact()
        if not contact or contact[0]==65535:return
        path,_=W.QFileDialog.getSaveFileName(self,'Export invitation for '+contact[1],contact[1]+'_invitation.json','JSON (*.json)')
        if not path:return
        try:Path(path).write_text(json.dumps(make_invitation(self.c,contact[0],contact[1]),indent=2)+'\n')
        except OSError as exc:W.QMessageBox.warning(self,'Invitation',str(exc));return
        self.details_note.setText('Invitation exported. Give it only to this person; it includes the network key and their assigned address. They should run the app without --config to import it on first launch.');self.show_radio_details()

    def import_contact(self):
        path,_=W.QFileDialog.getOpenFileName(self,'Import an existing node setup','','JSON (*.json)')
        if not path:return
        try:
            c=json.loads(Path(path).read_text())
            if c.get('format')=='pixel-pulse-contact':
                c=parse_contact(c,self.c);c['shared_key']=self.c['shared_key']
            address=int(c['address'])
            if address==self.c['address'] or not 1<=address<65535:raise ValueError('Address conflicts with this node or is reserved')
            if c.get('shared_key')!=self.c['shared_key']:raise ValueError('This node belongs to a different encryption network')
            if self.db.execute('SELECT 1 FROM contacts WHERE address=?',(address,)).fetchone():raise ValueError('That contact address already exists')
            self.db.execute('INSERT INTO contacts VALUES(?,?,1)',(address,c['name']));self.db.execute('INSERT OR IGNORE INTO address_reservations VALUES(?)',(address,));self.db.commit();self.refresh_contacts()
        except Exception as exc:W.QMessageBox.warning(self,'Import contact',str(exc))

    def command(self,cmd):
        try:self.tx.send_json(cmd,zmq.NOBLOCK);return True
        except zmq.Again:return False

    def send_text(self):
        text=self.composer.toPlainText()
        if not text.strip():return
        if len(text.encode())>65536:W.QMessageBox.warning(self,'Message','Maximum text size is 64 KiB');return
        if self.submit('text',text):self.composer.clear()

    def attach_file(self):
        if self.selected is None:return
        path,_=W.QFileDialog.getOpenFileName(self,'Attach image, audio, or file')
        if not path:return
        suffix=Path(path).suffix.lower();kind='image' if suffix in ('.png','.jpg','.jpeg','.webp','.gif','.bmp') else 'audio' if suffix in ('.wav','.mp3','.ogg','.opus','.flac','.m4a') else 'file'
        try:
            if not 0<Path(path).stat().st_size<=16*1024*1024:raise ValueError('File must be nonempty and at most 16 MiB')
            worker=AttachmentWorker(path,kind,self.c['state_dir'],self.contact())
            worker.prepared.connect(self.attachment_ready);worker.finished.connect(lambda:self.clean_workers())
            self.workers.append(worker);worker.start();self.notice.setText('Preparing attachment in the background… You can continue chatting.')
        except Exception as exc:W.QMessageBox.warning(self,'Attachment',str(exc))

    def clean_workers(self):
        self.workers=[w for w in self.workers if w.isRunning()]

    def attachment_ready(self,result):
        if 'error' in result:W.QMessageBox.warning(self,'Attachment',result['error'])
        else:self.submit(result['kind'],result['name'],result['path'],result['contact'])

    def submit(self,kind,body,path='',contact=None):
        contact=contact or self.contact()
        if not contact:W.QMessageBox.information(self,'Contact','Add or select a contact first');return False
        ident=str(uuid.uuid4());cmd=dict(cmd='send',id=ident,dst=contact[0],priority=contact[2],kind=kind)
        if kind=='text':cmd['text']=body
        else:cmd.update(path=path,name=body)
        self.db.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?,?,?,?)',(ident,contact[0],1,kind,body,path,'queued',time.time(),json.dumps(cmd),''));self.db.commit()
        self.command(cmd);self.refresh_contacts();self.render_history();return True

    def render_history(self):
        bar=self.scroll.verticalScrollBar();old=bar.value();at_bottom=bar.maximum()-old<60
        while self.history.count():
            item=self.history.takeAt(0)
            if item.widget():item.widget().hide();item.widget().deleteLater()
        rows=self.db.execute('SELECT id,outgoing,kind,body,path,status,stamp,detail FROM messages WHERE contact=? ORDER BY stamp',(self.selected,)).fetchall()
        self.history.addStretch()
        if not rows:
            empty=W.QLabel('A new conversation starts here\n\nSay hello. Your messages are saved on this device.');empty.setAlignment(QtCore.Qt.AlignCenter);empty.setObjectName('muted');self.history.addWidget(empty)
            self.history.addStretch()
        previous_day=None
        for ident,outgoing,kind,body,path,status,stamp,detail in rows:
            day=time.strftime('%d %B %Y',time.localtime(stamp))
            if day!=previous_day:
                date=W.QLabel('Today' if day==time.strftime('%d %B %Y') else day);date.setObjectName('date');date.setAlignment(QtCore.Qt.AlignCenter);self.history.addWidget(date);previous_day=day
            row=W.QWidget();layout=W.QHBoxLayout(row);layout.setContentsMargins(0,0,0,0)
            card=W.QFrame();card.setObjectName('sentBubble' if outgoing else 'receivedBubble')
            natural=max((self.fontMetrics().horizontalAdvance(line) for line in body.splitlines()),default=180)+40
            card.setFixedWidth(min(max(220,int(self.scroll.viewport().width()*.75)),max(220,min(540,natural))))
            content=W.QVBoxLayout(card);content.setContentsMargins(14,10,14,9)
            label=W.QLabel(body);label.setTextFormat(QtCore.Qt.PlainText);label.setWordWrap(True);label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse);content.addWidget(label)
            if path:
                if kind=='image':
                    reader=QtGui.QImageReader(path);size=reader.size()
                    if size.isValid() and size.width()*size.height()<=40_000_000:
                        reader.setScaledSize(size.scaled(300,180,QtCore.Qt.KeepAspectRatio));preview=W.QLabel();preview.setPixmap(QtGui.QPixmap.fromImage(reader.read()));content.addWidget(preview)
                b=W.QPushButton('Play audio' if kind=='audio' else 'Open file');b.clicked.connect(lambda _,p=path:QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(p)));content.addWidget(b)
            suffix={'queued':'Queued','sending':'Sending…','sent':'Sent · awaiting ACK' if self.selected!=65535 else 'Sent · broadcast','delivered':'✓✓ Delivered','failed':'Failed','received':'Received'}.get(status,status)
            footer=W.QLabel(time.strftime('%H:%M',time.localtime(stamp))+'  '+suffix);footer.setObjectName('muted');footer.setToolTip(detail);content.addWidget(footer)
            if outgoing and status=='failed':
                b=W.QPushButton('Retry');b.clicked.connect(lambda _,k=kind,t=body,p=path:self.submit(k,t,p));content.addWidget(b)
            if outgoing:layout.addStretch()
            layout.addWidget(card)
            if not outgoing:layout.addStretch()
            self.history.addWidget(row)
        QtCore.QTimer.singleShot(0,self.scroll_to_latest if at_bottom else lambda:bar.setValue(old))

    def poll(self):
        changed=False;now=time.monotonic()
        for _ in range(200):
            try:e=self.rx.recv_json(zmq.NOBLOCK)
            except zmq.Again:break
            self.last_event=now
            if e['event']=='status' and e.get('id'):
                prior=self.db.execute('SELECT status FROM messages WHERE id=? AND outgoing=1',(e['id'],)).fetchone()
                detail=e.get('reason','') or (f"Retry {e['retry']}" if e.get('retry') else '')
                self.db.execute('UPDATE messages SET status=?,detail=? WHERE id=? AND outgoing=1',(e['status'],detail,e['id']))
                changed|=bool(prior and prior[0]!=e['status'])
            elif e['event']=='received':
                if self.book.receive(e,read=self.conversation_visible(e['src'])):changed=True;self.refresh_contacts()
            elif e['event']=='telemetry':
                local=self.db.execute("SELECT count(*) FROM messages WHERE outgoing=1 AND status='queued'").fetchone()[0]
                self.queue_label.setText(f"{max(local,e['waiting'])} messages waiting")
                self.channel.setText(f"{'Busy' if e['busy'] else 'Idle'} · RX {e['power_db']:.1f} dB · {self.c['frequency']/1e9:g} GHz")
            elif e['event']=='diagnostic':self.details_note.setText(e['message'])
        self.db.commit()
        if changed:self.render_history()
        connected=bool(self.last_event) and now-self.last_event<2
        self.connection.setText('Connected' if connected else 'Offline · messages stay queued')
        if now-self.last_hello>5:
            self.command(dict(cmd='hello'));self.last_hello=now
        if now-self.last_resend>2:
            for row in self.db.execute("SELECT command FROM messages WHERE outgoing=1 AND status IN ('queued','sending','sent')"):
                if row[0]:self.command(json.loads(row[0]))
            self.last_resend=now

    def closeEvent(self,event):
        if self.workers:
            self.notice.setText('Finishing attachment preparation before closing…');event.ignore();return
        self.timer.stop();self.tx.close();self.rx.close();self.ctx.term();self.db.close();event.accept()


def main():
    p=argparse.ArgumentParser();p.add_argument('--config');a=p.parse_args()
    app=W.QApplication(sys.argv);app.setApplicationName('Pixel Pulse');app.setApplicationDisplayName('Pixel Pulse')
    app.setWindowIcon(QtGui.QIcon(str(Path(__file__).resolve().parents[1]/'assets/pixel-pulse.svg')))
    path=Path(a.config) if a.config else Path(__file__).resolve().parents[1]/'configs/my_node.json'
    if not a.config and not path.exists():
        if WelcomeDialog(path).exec_()!=W.QDialog.Accepted:return
    from .radio_setup import configure_radio
    if not configure_radio(path):return
    config=load(path)
    window=Window(config);window.show()
    from .radio_process import attach_radio
    radio=attach_radio(app,window,config)
    for signum in (signal.SIGINT,signal.SIGTERM):
        signal.signal(signum,lambda *_:app.quit())
    signal_timer=QtCore.QTimer(app);signal_timer.timeout.connect(lambda:None);signal_timer.start(200)
    try:result=app.exec_()
    finally:radio.stop()
    sys.exit(result)


if __name__=='__main__':main()
