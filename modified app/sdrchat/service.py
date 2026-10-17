"""ZMQ app boundary. All sockets and Engine methods belong to one thread."""
import queue
import threading
import time
import zmq
from .engine import Engine


class Service:
    def __init__(self, config, transmit, incoming=None, sensor=None, transport_tick=None):
        self.c=config;self.transmit=transmit;self.incoming=incoming or queue.Queue()
        self.sensor=sensor;self.transport_tick=transport_tick;self.stop_event=threading.Event()
        self.ready=threading.Event();self.error=None;self.thread=None

    def start(self):
        self.thread=threading.Thread(target=self.run,name='radio-mac',daemon=True);self.thread.start()
        if not self.ready.wait(5):raise RuntimeError('Radio service did not start')
        if self.error:raise RuntimeError(str(self.error))

    def stop(self):
        self.stop_event.set()
        if self.thread:self.thread.join(5)

    def run(self):
        context=zmq.Context();commands=context.socket(zmq.PULL);events=context.socket(zmq.PUSH)
        commands.setsockopt(zmq.MAXMSGSIZE,1024*1024)
        for s in (commands,events):s.setsockopt(zmq.LINGER,0)
        engine=None
        try:
            commands.bind('tcp://127.0.0.1:'+str(self.c['commands_port']))
            events.bind('tcp://127.0.0.1:'+str(self.c['events_port']))
            def emit(event):
                try:events.send_json(event,zmq.NOBLOCK)
                except zmq.Again:pass # Durable snapshot recovers message events on reconnect.
            engine=Engine(self.c,self.transmit,emit)
            self.ready.set()
            while not self.stop_event.is_set():
                if self.transport_tick:self.transport_tick(engine)
                if self.sensor:
                    reading=self.sensor()
                    if reading is not None:engine.sense(*reading)
                for _ in range(100):
                    try:engine.receive(self.incoming.get_nowait())
                    except queue.Empty:break
                for _ in range(100):
                    try:cmd=commands.recv_json(zmq.NOBLOCK)
                    except zmq.Again:break
                    try:
                        if cmd.get('cmd')=='send':engine.enqueue(cmd)
                        elif cmd.get('cmd')=='hello':engine.snapshot()
                        elif cmd.get('cmd')=='threshold':
                            value=float(cmd['db'])
                            if not -140<=value<=20:raise ValueError('Threshold outside -140..20 dB')
                            engine.c['cs_threshold_db']=value
                    except Exception as exc:
                        emit(dict(event='status',id=cmd.get('id'),status='failed',reason=str(exc)))
                engine.tick();self.stop_event.wait(0.003)
        except Exception as exc:
            self.error=exc;self.ready.set();print('Radio service stopped:',exc,flush=True)
        finally:
            if engine:engine.close()
            commands.close();events.close();context.term()
