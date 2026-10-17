import ctypes
import hashlib
from pathlib import Path
import numpy as np
import pmt
from gnuradio import gr


def training_bytes(length=2048):
    return b''.join(hashlib.sha256(b'QPSK-training-v1'+i.to_bytes(4,'big')).digest()
                    for i in range((length+31)//32))[:length]


def training_symbols():
    # Last 64 bytes of the EXISTING deterministic prefix. Constant differential
    # phase before this segment is absorbed by training; no change to TX bytes.
    bits=np.unpackbits(np.frombuffer(training_bytes()[-64:],dtype=np.uint8)).reshape(-1,2)
    chunks=bits[:,0]*2+bits[:,1]
    mapped=np.array([0,1,3,2])[chunks]
    index=np.cumsum(mapped)%4
    return np.array([.707+.707j,-.707+.707j,-.707-.707j,.707-.707j],np.complex64)[index]


class TrainingCorrelator(gr.sync_block):
    def __init__(self, threshold=.6):
        gr.sync_block.__init__(self,name='QPSK training correlator',in_sig=[np.complex64],out_sig=[np.complex64])
        symbols=training_symbols()[:64]
        t=np.arange(-8,9)/2.;a=.35
        pulse=np.sinc(t)*np.cos(np.pi*a*t)/(1-(2*a*t)**2)
        self.ref=np.convolve(np.kron(symbols,[1,0]),pulse)[8:8+2*len(symbols)-1].astype(np.complex64)
        self.energy=float(np.vdot(self.ref,self.ref).real);self.threshold=threshold
        self.delay=(len(self.ref)+9)//2*2
        self.set_history(self.delay+1);self.set_tag_propagation_policy(gr.TPP_DONT)
        self.next_position=0;self.last_position=-10000;self.count=0

    def work(self, inputs, outputs):
        x=inputs[0];out=outputs[0];n=len(out);out[:]=x[:n]
        base=self.nitems_written(0)-self.delay
        c=np.correlate(x,self.ref,'valid')
        power=np.convolve(np.abs(x).astype(np.float64)**2,np.ones(len(self.ref)),'valid')
        score=np.abs(c)**2/(self.energy*power+1e-12)
        lo=max(self.next_position-base,2,-base);hi=min(len(score)-3,n+self.delay-len(self.ref))
        for j in np.flatnonzero(score[lo:hi+1]>self.threshold)+lo:
            if score[j]<max(score[j-2:j]) or score[j]<=max(score[j+1:j+3]):continue
            absolute=base+int(j)
            if absolute-self.last_position<512:continue
            offset=absolute+self.delay
            if offset<self.nitems_written(0):continue
            self.add_item_tag(0,offset,pmt.intern('corr_est'),pmt.from_double(float(score[j])))
            self.last_position=absolute;self.count+=1
        if hi>=lo:self.next_position=base+hi+1
        return n


class NLMS(gr.decim_block):
    def __init__(self,taps=7,mu=.2,dd_mu=.02,eps=1e-6):
        gr.decim_block.__init__(self,name='Regularized QPSK NLMS',in_sig=[np.complex64],out_sig=[np.complex64],decim=2)
        if taps<3 or taps%2!=1 or not 0<mu<2 or not 0<dd_mu<2 or eps<=0:raise ValueError('Invalid NLMS parameters')
        self.taps=taps;self.mu=mu;self.dd_mu=dd_mu;self.eps=eps
        self.weights=np.zeros(taps,np.complex64);self.weights[0]=1
        self.training=training_symbols();self.pos=ctypes.c_int(0);self.active=ctypes.c_int(0)
        lib=Path(__file__).parent/'native'/'libnlms.so'
        if not lib.exists():raise RuntimeError('Run ./setup.sh to build the NLMS kernel')
        self.lib=ctypes.CDLL(str(lib));self.fn=self.lib.nlms_process
        self.fn.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_void_p,
            ctypes.c_void_p,ctypes.c_int,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),
            ctypes.c_float,ctypes.c_float,ctypes.c_float,ctypes.c_float,ctypes.c_void_p,ctypes.c_int]
        self.fn.restype=None;self.set_history(taps);self.set_tag_propagation_policy(gr.TPP_DONT)

    def work(self,inputs,outputs):
        x=inputs[0];y=outputs[0];n=len(y)
        tags=self.get_tags_in_window(0,0,2*n,pmt.intern('corr_est'))
        starts=np.array([int(t.offset-self.nitems_read(0)) for t in tags],np.int32)
        self.fn(x.ctypes.data,y.ctypes.data,n,self.taps,self.weights.ctypes.data,
                self.training.ctypes.data,len(self.training),ctypes.byref(self.pos),ctypes.byref(self.active),
                self.mu,self.dd_mu,self.eps,1e-8,starts.ctypes.data,len(starts))
        return n
