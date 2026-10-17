"""Network-order routing header + authenticated encrypted fragment or ACK.

The GNU Radio graph adds CRC32 and RS outside this layer. The simulator uses
the same CRC and RS codec. Routing fields are repeated inside Fernet so they
cannot be altered without authentication failure.
"""
import hashlib
import json
import struct
import uuid
import zlib
from cryptography.fernet import Fernet
from .reedsolo_bundled import RSCodec

TEXT, ACK = 1, 2
BROADCAST = 0xFFFF
HEADER = struct.Struct('!HHIBBH')
ROUTE = struct.Struct('!HHIBB')
FRAGMENT = struct.Struct('!16sHHH')


class Codec:
    def __init__(self, key):
        self.cipher = Fernet(key.encode() if isinstance(key, str) else key)
        self.rs = RSCodec(16, nsize=255, fcr=0, prim=0x11d, generator=2, c_exp=8)

    def pack(self, dst, src, seq, priority, typ, body):
        if not 1 <= src < BROADCAST or not 1 <= dst <= BROADCAST:
            raise ValueError('Invalid address')
        if priority not in (0, 1, 2) or typ not in (TEXT, ACK):
            raise ValueError('Invalid priority or packet type')
        route = ROUTE.pack(dst, src, seq, priority, typ)
        token = self.cipher.encrypt(route + body)
        wire = HEADER.pack(dst, src, seq, priority, typ, len(token)) + token
        if len(wire) > 4092:
            raise ValueError('Frame exceeds original 4092-byte budget')
        return wire

    def unpack(self, wire, me):
        if len(wire) < HEADER.size or len(wire) > 4092:
            raise ValueError('Invalid frame size')
        dst, src, seq, pri, typ, length = HEADER.unpack_from(wire)
        if dst not in (me, BROADCAST) or src == me or not 1 <= src < BROADCAST:
            raise ValueError('Frame for another node or own echo')
        if length != len(wire)-HEADER.size or pri not in (0,1,2) or typ not in (TEXT,ACK):
            raise ValueError('Malformed header')
        raw = self.cipher.decrypt(wire[HEADER.size:])
        if raw[:ROUTE.size] != ROUTE.pack(dst,src,seq,pri,typ):
            raise ValueError('Authenticated routing mismatch')
        return dict(dst=dst, src=src, seq=seq, priority=pri, typ=typ, body=raw[ROUTE.size:])

    def protect(self, raw):
        data = raw + struct.pack('!I', zlib.crc32(raw))
        return bytes(self.rs.encode(data))

    def recover(self, coded):
        data = bytes(self.rs.decode(coded)[0])
        if len(data)<4 or zlib.crc32(data[:-4]) != struct.unpack('!I',data[-4:])[0]:
            raise ValueError('CRC failure')
        return data[:-4]


def make_fragment(job, index):
    data = job['data']
    chunk = 128 if job['kind']=='text' else 1024
    count = max(1, (len(data)+chunk-1)//chunk)
    meta = json.dumps(dict(kind=job['kind'], name=job['name'], size=len(data),
                           sha256=hashlib.sha256(data).hexdigest()),separators=(',',':')).encode()
    return FRAGMENT.pack(uuid.UUID(job['id']).bytes,index,count,len(meta))+meta+data[index*chunk:(index+1)*chunk], count


def parse_fragment(body):
    if len(body)<FRAGMENT.size:
        raise ValueError('Truncated fragment')
    ident,index,count,mlen = FRAGMENT.unpack_from(body)
    if not 1<=count<=16384 or index>=count or not 0<mlen<=1024:
        raise ValueError('Invalid fragmentation')
    meta = json.loads(body[FRAGMENT.size:FRAGMENT.size+mlen])
    if meta['kind'] not in ('text','image','audio','file') or not 0<meta['size']<=16*1024*1024:
        raise ValueError('Invalid transfer metadata')
    chunk = 128 if meta['kind']=='text' else 1024
    if meta['kind']=='text' and meta['size']>65536:
        raise ValueError('Text exceeds original 64 KiB limit')
    if count != (meta['size']+chunk-1)//chunk:
        raise ValueError('Wrong fragment count')
    data=body[FRAGMENT.size+mlen:]
    if len(data)!=min(chunk,meta['size']-index*chunk):
        raise ValueError('Wrong fragment length')
    return str(uuid.UUID(bytes=ident)),index,count,meta,data
