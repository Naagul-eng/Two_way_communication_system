"""Durable, single-flight ARQ with CSMA/CA. Owned by the radio process."""
import hashlib
import json
import random
import sqlite3
import time
import uuid
from collections import deque
from pathlib import Path
from cryptography.fernet import InvalidToken
from .protocol import Codec, TEXT, ACK, BROADCAST, make_fragment, parse_fragment


class Engine:
    def __init__(self, config, transmit, event, clock=time.monotonic, rng=None):
        self.c=config; self.me=config['address']; self.transmit=transmit; self.event=event
        self.clock=clock; self.rng=rng or random.SystemRandom(); self.codec=Codec(config['shared_key'])
        self.db=sqlite3.connect(str(Path(config['state_dir'])/'radio.sqlite'))
        self.db.execute('PRAGMA journal_mode=WAL'); self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,dst INTEGER,priority INTEGER,kind TEXT,name TEXT,data BLOB,created REAL,status TEXT,part INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS fragments(src INTEGER,id TEXT,part INTEGER,total INTEGER,meta TEXT,data BLOB,PRIMARY KEY(src,id,part));
        CREATE TABLE IF NOT EXISTS receipts(src INTEGER,seq INTEGER,digest TEXT,PRIMARY KEY(src,seq));
        CREATE TABLE IF NOT EXISTS received(src INTEGER,id TEXT,kind TEXT,name TEXT,data BLOB,PRIMARY KEY(src,id));
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value INTEGER);
        ''')
        self.db.execute("INSERT OR IGNORE INTO settings VALUES('sequence',?)",(self.rng.randrange(1,2**30),))
        self.db.execute("UPDATE jobs SET status='queued' WHERE status IN ('sending','sent')")
        self.db.commit()
        self.queues=[deque(),deque(),deque()]
        self.jobs={}; self.current=None; self.flight=None; self.acks=deque(); self.ack_keys=set()
        self.contender=None; self.idle_since=None; self.tx_until=0; self.busy=True
        self.power=-200.; self.sense_at=-1e9; self.last_status=-1e9
        for row in self.db.execute("SELECT id,dst,priority,kind,name,data,created,part FROM jobs WHERE status='queued' ORDER BY created,rowid"):
            j=dict(zip(('id','dst','priority','kind','name','data','created','part'),row))
            j['enqueued']=self.clock()-max(0,time.time()-j['created']); self.jobs[j['id']]=j
            self.queues[j['priority']].append(j)

    def close(self):
        self.db.close()

    def status(self, ident, state, **extra):
        self.db.execute('UPDATE jobs SET status=? WHERE id=?',(state,ident)); self.db.commit()
        self.event(dict(event='status',id=ident,status='sent' if state=='broadcast_sent' else state,**extra))

    def enqueue(self, command):
        ident=str(uuid.UUID(command['id']))
        found=self.db.execute('SELECT status FROM jobs WHERE id=?',(ident,)).fetchone()
        if found:
            self.event(dict(event='status',id=ident,status='sent' if found[0]=='broadcast_sent' else found[0])); return
        dst=int(command['dst']); pri=int(command['priority']); kind=command['kind']
        if dst==self.me or not 1<=dst<=BROADCAST or pri not in (0,1,2):
            raise ValueError('Invalid destination or priority')
        if kind=='text':
            data=command['text'].encode('utf-8'); name='message.txt'
            if not 0<len(data)<=65536: raise ValueError('Text must contain 1..65536 UTF-8 bytes')
        elif kind in ('image','audio','file'):
            p=Path(command['path']).resolve()
            if not p.is_file() or not 0<p.stat().st_size<=16*1024*1024:
                raise ValueError('Choose a nonempty file up to 16 MiB')
            data=p.read_bytes(); name=str(command.get('name',p.name))[:120]
        else: raise ValueError('Unknown message type')
        j=dict(id=ident,dst=dst,priority=pri,kind=kind,name=name,data=data,
               created=time.time(),part=0,enqueued=self.clock())
        self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',
            (ident,dst,pri,kind,name,data,j['created'],'queued',0)); self.db.commit()
        self.jobs[ident]=j; self.queues[pri].append(j)
        self.status(ident,'queued')

    def snapshot(self):
        for ident,status in self.db.execute('SELECT id,status FROM jobs'):
            self.event(dict(event='status',id=ident,status='sent' if status=='broadcast_sent' else status))
        for src,ident,kind,name,data in self.db.execute('SELECT src,id,kind,name,data FROM received'):
            self.deliver_event(src,ident,kind,name,data)

    def deliver_event(self, src, ident, kind, name, data):
        info=dict(event='received',id=ident,src=src,kind=kind,name=name)
        if kind=='text': info['text']=data.decode('utf-8')
        else:
            directory=Path(self.c['state_dir'])/'received'; directory.mkdir(exist_ok=True)
            safe=''.join(c if c.isalnum() or c in '.-_ ' else '_' for c in Path(name).name)[:120]
            path=directory/(str(src)+'_'+ident+'_'+safe)
            if not path.exists():
                temp=path.with_suffix(path.suffix+'.part');temp.write_bytes(data);temp.replace(path)
            info['path']=str(path)
        self.event(info)

    def sense(self, power_db, busy=None):
        self.power=float(power_db); self.sense_at=self.clock()
        if busy is None:
            limit=self.c['cs_threshold_db']-(self.c['cs_hysteresis_db'] if self.busy else 0)
            self.busy=self.power>limit
        else:self.busy=bool(busy)
        if self.busy:
            self.idle_since=None
            if self.contender:self.contender.pop('slot_at',None)

    def receive(self, wire):
        try:
            f=self.codec.unpack(wire,self.me)
            if f['typ']==ACK:
                p=self.flight
                if p and p.get('sent_once') and f['dst']==self.me and f['src']==p['dst'] and f['seq']==p['seq'] and f['body']==uuid.UUID(self.current['id']).bytes:
                    self.complete_packet()
                return
            digest=hashlib.sha256(wire).hexdigest()
            receipt=self.db.execute('SELECT digest FROM receipts WHERE src=? AND seq=?',(f['src'],f['seq'])).fetchone()
            ident,index,count,meta,data=parse_fragment(f['body'])
            if receipt and receipt[0]!=digest: return
            if not receipt:
                # Completed messages may be retransmitted with a new sequence after a restart.
                done=self.db.execute('SELECT 1 FROM received WHERE src=? AND id=?',(f['src'],ident)).fetchone()
                if not done:
                    m=json.dumps(meta,sort_keys=True)
                    existing=self.db.execute('SELECT meta,data FROM fragments WHERE src=? AND id=? AND part=?',(f['src'],ident,index)).fetchone()
                    if existing and existing!=(m,data):raise ValueError('Conflicting fragment')
                    other=self.db.execute('SELECT meta FROM fragments WHERE src=? AND id=? LIMIT 1',(f['src'],ident)).fetchone()
                    if other and other[0]!=m:raise ValueError('Conflicting metadata')
                    self.db.execute('INSERT OR IGNORE INTO fragments VALUES(?,?,?,?,?,?)',(f['src'],ident,index,count,m,data))
                    rows=self.db.execute('SELECT data FROM fragments WHERE src=? AND id=? ORDER BY part',(f['src'],ident)).fetchall()
                    if len(rows)==count:
                        full=b''.join(r[0] for r in rows)
                        if len(full)!=meta['size'] or hashlib.sha256(full).hexdigest()!=meta['sha256']:
                            raise ValueError('Whole-message SHA-256 failure')
                        if meta['kind']=='text':full.decode('utf-8')
                        self.db.execute('INSERT INTO received VALUES(?,?,?,?,?)',(f['src'],ident,meta['kind'],meta['name'],full))
                        self.db.execute('DELETE FROM fragments WHERE src=? AND id=?',(f['src'],ident))
                self.db.execute('INSERT INTO receipts VALUES(?,?,?)',(f['src'],f['seq'],digest)); self.db.commit()
                # Reconstruct delivery event from durable storage, before acknowledging completion.
                received=self.db.execute('SELECT kind,name,data FROM received WHERE src=? AND id=?',(f['src'],ident)).fetchone()
                if received:self.deliver_event(f['src'],ident,*received)
            if f['dst']!=BROADCAST and (f['src'],f['seq']) not in self.ack_keys:
                self.ack_keys.add((f['src'],f['seq']))
                raw=self.codec.pack(f['src'],self.me,f['seq'],0,ACK,uuid.UUID(ident).bytes)
                self.acks.append(dict(wire=raw,ack=True,dst=f['src'],seq=f['seq'],cw=4,slots=None))
        except (ValueError,KeyError,TypeError,InvalidToken,UnicodeError) as exc:
            self.db.rollback()
            self.event(dict(event='diagnostic',message='RX rejected: '+str(exc)))

    def choose(self):
        now=self.clock()
        heads=[(max(0,p-int((now-q[0]['enqueued'])/self.c['aging_s'])),q[0]['created'],p) for p,q in enumerate(self.queues) if q]
        if not heads:return None
        _,_,p=min(heads)
        return self.queues[p].popleft()

    def new_packet(self):
        j=self.current
        seq=self.db.execute("SELECT value FROM settings WHERE key='sequence'").fetchone()[0]
        if seq>=0xFFFFFFFF:raise RuntimeError('Sequence space exhausted; provision a new node address')
        self.db.execute("UPDATE settings SET value=? WHERE key='sequence'",(seq+1,));self.db.commit()
        body,count=make_fragment(j,j['part'])
        self.flight=dict(wire=self.codec.pack(j['dst'],self.me,seq,j['priority'],TEXT,body),
                         dst=j['dst'],seq=seq,retries=0,cw=self.c['cw_min'][j['priority']],slots=None,
                         deadline=None,ack=False,count=count)

    def complete_packet(self):
        j=self.current;p=self.flight
        if self.contender is p:self.contender=None
        j['part']+=1
        self.db.execute('UPDATE jobs SET part=? WHERE id=?',(j['part'],j['id']));self.db.commit()
        self.flight=None
        if j['part']>=p['count']:
            self.status(j['id'],'broadcast_sent' if j['dst']==BROADCAST else 'delivered',broadcast=j['dst']==BROADCAST)
            self.jobs.pop(j['id'],None);self.current=None
        else:
            self.status(j['id'],'sending',progress=j['part']/p['count'])
            self.queues[j['priority']].appendleft(j);self.current=None

    def tick(self):
        now=self.clock()
        if now-self.last_status>=0.5:
            self.event(dict(event='telemetry',power_db=self.power,busy=self.busy,
                            waiting=sum(map(len,self.queues)),active=bool(self.current),
                            queues=[len(q) for q in self.queues],address=self.me))
            self.last_status=now
        if now<self.tx_until:
            self.idle_since=None;return
        if self.flight and self.flight.get('broadcast_done'):
            self.complete_packet()
        if self.flight and self.flight['deadline'] is not None and now>=self.flight['deadline']:
            p=self.flight
            if p['retries']>=self.c['retry_limit']:
                self.status(self.current['id'],'failed',reason='ACK timeout: retry limit reached')
                self.jobs.pop(self.current['id'],None);self.current=None;self.flight=None
                if self.contender is p:self.contender=None
            else:
                p['retries']+=1;p['cw']=min(self.c['cw_max'],p['cw']*2)
                p['deadline']=None;p['slots']=None
                self.status(self.current['id'],'sending',retry=p['retries'])
        if self.current is None:
            self.current=self.choose()
        if self.current and self.flight is None:self.new_packet()
        # ACKs have a separate control queue. They never wait behind a data ACK timeout.
        if self.acks:
            candidate=self.acks[0]
        elif self.flight and self.flight['deadline'] is None:
            candidate=self.flight
        else:
            self.contender=None;return
        if candidate is not self.contender:
            self.contender=candidate; self.idle_since=None;candidate.pop('slot_at',None)
        if self.busy or now-self.sense_at>0.2:
            self.idle_since=None;candidate.pop('slot_at',None);return
        if self.idle_since is None:self.idle_since=now
        if now-self.idle_since<self.c['difs_s']:return
        if candidate['slots'] is None:
            candidate['slots']=self.rng.randrange(candidate['cw']);candidate['slot_at']=now
        elif 'slot_at' not in candidate:candidate['slot_at']=now
        slots=int((now-candidate['slot_at'])/self.c['slot_s'])
        candidate['slots']=max(0,candidate['slots']-slots)
        candidate['slot_at']+=slots*self.c['slot_s']
        if candidate['slots']:return
        if not candidate['ack']:self.status(self.current['id'],'sending')
        try:duration=float(self.transmit(candidate['wire']))
        except Exception as exc:
            self.event(dict(event='diagnostic',message='TX unavailable: '+str(exc)))
            candidate['slots']=None;self.idle_since=None;return
        self.tx_until=now+duration;self.idle_since=None;self.contender=None
        if candidate['ack']:
            self.acks.popleft();self.ack_keys.discard((candidate['dst'],candidate['seq']))
        else:
            candidate['sent_once']=True
            candidate['deadline']=self.tx_until+self.c['ack_timeout_s']
            if candidate['dst']==BROADCAST:candidate['broadcast_done']=True
            self.status(self.current['id'],'sent',retry=candidate['retries'])
