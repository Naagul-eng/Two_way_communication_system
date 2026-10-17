import json
from pathlib import Path
import random
import tempfile
import unittest
import uuid
from cryptography.fernet import InvalidToken
from sdrchat.protocol import Codec,HEADER,ACK,TEXT,BROADCAST
from sdrchat.engine import Engine

BASE=json.loads((Path(__file__).parents[1]/'configs/node_a.example.json').read_text())


class Network:
    def __init__(self):
        self.tmp=tempfile.TemporaryDirectory();self.now=0.;self.nodes=[];self.events=[];self.air=[];self.drop=0;self.frames=[]
    def node(self,address):
        c=dict(BASE,address=address,state_dir=self.tmp.name+'/'+str(address),difs_s=.02,slot_s=.01,ack_timeout_s=.15,retry_limit=2,aging_s=.3)
        Path(c['state_dir']).mkdir();index=len(self.nodes);events=[]
        def transmit(wire):
            self.frames.append((address,wire));collision=bool(self.air)
            for frame in self.air:frame['collision']=True
            self.air.append(dict(sender=index,wire=wire,end=self.now+.02,collision=collision))
            return .02
        n=Engine(c,transmit,events.append,clock=lambda:self.now,rng=random.Random(address))
        self.nodes.append(n);self.events.append(events);return n
    def run(self,duration):
        for _ in range(int(duration/.005)):
            self.now+=.005
            for f in list(self.air):
                if self.now>=f['end']:
                    self.air.remove(f)
                    if self.drop:self.drop-=1;continue
                    if not f['collision']:
                        for i,n in enumerate(self.nodes):
                            if i!=f['sender']:n.receive(f['wire'])
            for n in self.nodes:n.sense(-20 if self.air else -80,bool(self.air));n.tick()
    def close(self):
        for n in self.nodes:n.close()
        self.tmp.cleanup()


def command(dst,text='Hello',priority=1):
    return dict(id=str(uuid.uuid4()),dst=dst,priority=priority,kind='text',text=text)


class ProtocolTests(unittest.TestCase):
    def test_crc_rs_authentication(self):
        c=Codec(BASE['shared_key']);raw=c.pack(2,1,123,0,TEXT,b'payload')
        coded=bytearray(c.protect(raw))
        for i in range(8):coded[2*i]^=0x55
        self.assertEqual(c.recover(coded),raw)
        self.assertEqual(c.unpack(raw,2)['body'],b'payload')
        with self.assertRaises(ValueError):c.unpack(raw,3)
        forged=bytearray(raw);forged[4]^=1
        with self.assertRaises((ValueError,InvalidToken)):c.unpack(bytes(forged),2)

    def test_three_nodes_queue_and_duplicates(self):
        net=Network();a=net.node(1);b=net.node(2);c=net.node(3)
        try:
            ids=[]
            for dest,text in [(2,'first'),(3,'second'),(2,'third')]:
                cmd=command(dest,text);ids.append(cmd['id']);a.enqueue(cmd)
            b.enqueue(command(1,'reverse'))
            net.run(12)
            self.assertEqual([r[0] for r in a.db.execute('SELECT status FROM jobs')],['delivered']*3)
            self.assertEqual(b.db.execute('SELECT count(*) FROM received').fetchone()[0],2)
            self.assertEqual(c.db.execute('SELECT count(*) FROM received').fetchone()[0],1)
            self.assertEqual(a.db.execute('SELECT count(*) FROM received').fetchone()[0],1)
            raw=next(raw for sender,raw in net.frames if sender==1 and HEADER.unpack_from(raw)[0]==2)
            b.receive(raw);b.receive(raw)
            self.assertEqual(b.db.execute('SELECT count(*) FROM received').fetchone()[0],2)
        finally:net.close()

    def test_fragmented_text_and_lost_ack(self):
        net=Network();a=net.node(1);b=net.node(2)
        try:
            content='Unicode: தமிழ் ✓ '*40;a.enqueue(command(2,content))
            net.drop=1;net.run(20)
            self.assertEqual(a.db.execute('SELECT status FROM jobs').fetchone()[0],'delivered')
            self.assertEqual(b.db.execute('SELECT data FROM received').fetchone()[0].decode(),content)
            # Drop ACK after successful receipt, force retry and ensure one delivery.
            a.enqueue(command(2,'lost ack'))
            dropped=False
            for _ in range(1000):
                if any(HEADER.unpack_from(f['wire'])[4]==ACK for f in net.air) and not dropped:
                    net.drop=1;dropped=True
                net.run(.01)
            self.assertTrue(dropped)
            self.assertEqual(b.db.execute('SELECT count(*) FROM received').fetchone()[0],2)
            self.assertEqual(a.db.execute("SELECT count(*) FROM jobs WHERE status='delivered'").fetchone()[0],2)
        finally:net.close()

    def test_backoff_freezes_and_window_doubles(self):
        net=Network();a=net.node(1)
        try:
            a.enqueue(command(2));a.tick();p=a.flight;p['slots']=5
            for i in range(100):net.now+=.005;a.sense(-20,True);a.tick()
            self.assertEqual(p['slots'],5);self.assertEqual(len(net.frames),0)
            net.run(.02);self.assertEqual(p['slots'],5)
            net.run(5)
            self.assertEqual(p['cw'],min(BASE['cw_max'],BASE['cw_min'][1]*4))
            self.assertEqual(a.db.execute('SELECT status FROM jobs').fetchone()[0],'failed')
            self.assertEqual(len(net.frames),3)
        finally:net.close()

    def test_priority_aging_and_fifo(self):
        net=Network();a=net.node(1)
        try:
            low=command(2,'low',2);a.enqueue(low);net.now+=1
            high=command(2,'high',0);a.enqueue(high)
            self.assertEqual(a.choose()['id'],low['id'])
            self.assertEqual(a.choose()['id'],high['id'])
            x=command(2,'x',1);y=command(2,'y',1);z=command(2,'z',0)
            for cmd in (x,y,z):a.enqueue(cmd)
            self.assertEqual([a.choose()['id'] for _ in range(3)],[z['id'],x['id'],y['id']])
        finally:net.close()

    def test_ack_preemption_preserves_data_backoff(self):
        net=Network();a=net.node(1)
        try:
            a.enqueue(command(2));a.sense(-80,False);a.tick()
            p=a.flight;p['slots']=7;p['slot_at']=net.now
            # An inbound frame inserts an ACK ahead of a data contention attempt.
            other=Codec(BASE['shared_key'])
            from sdrchat.protocol import make_fragment
            msg=dict(id=str(uuid.uuid4()),kind='text',name='message.txt',data=b'incoming')
            body,_=make_fragment(msg,0)
            a.receive(other.pack(1,2,999,1,TEXT,body))
            net.run(.2)
            self.assertLessEqual(p['slots'],7)
            # Returning to DATA contention starts a fresh slot clock after DIFS;
            # time spent serving ACK must not be subtracted from its backoff.
            p['slots']=7;p['slot_at']=net.now-10;a.contender=None
            a.sense(-80,False);a.tick();net.now+=.025;a.sense(-80,False);a.tick()
            self.assertEqual(p['slots'],7)
        finally:net.close()

    def test_broadcast_no_ack_and_restart_queue(self):
        net=Network();a=net.node(1);b=net.node(2);c=net.node(3)
        try:
            cmd=command(BROADCAST,'all');a.enqueue(cmd);a.enqueue(cmd)
            self.assertEqual(a.db.execute('SELECT count(*) FROM jobs').fetchone()[0],1)
            net.run(3)
            self.assertEqual(a.db.execute('SELECT status FROM jobs').fetchone()[0],'broadcast_sent')
            self.assertEqual(len(net.frames),1)
            self.assertEqual(b.db.execute('SELECT count(*) FROM received').fetchone()[0],1)
            self.assertEqual(c.db.execute('SELECT count(*) FROM received').fetchone()[0],1)
            a.enqueue(command(2));a.close()
            a=Engine(a.c,lambda w:.02,lambda e:None,clock=lambda:net.now);net.nodes[0]=a
            self.assertEqual(sum(map(len,a.queues)),1)
        finally:net.close()


if __name__=='__main__':unittest.main()
