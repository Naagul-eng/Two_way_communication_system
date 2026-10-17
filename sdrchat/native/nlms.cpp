// Batched regularized complex NLMS. y = w^H x, e = d-y.
#include <complex>
#include <cmath>
#include <algorithm>
using C = std::complex<float>;
extern "C" void nlms_process(const C* input, C* output, int n, int taps,
                              C* weights, const C* training, int training_len,
                              int* training_pos, int* active, float mu,
                              float dd_mu, float eps, float gate,
                              const int* starts, int nstarts) {
    int tag=0;
    for(int i=0;i<n;i++) {
        if(tag<nstarts && starts[tag]<=2*i+1) {
            *training_pos=0;*active=1;tag++;
            std::fill(weights,weights+taps,C(0,0));weights[0]=C(1,0);
        }
        const C* newest=input+taps-1+2*i;
        C y(0,0);float power=0;
        for(int k=0;k<taps;k++) {y+=std::conj(weights[k])*newest[-k];power+=std::norm(newest[-k]);}
        output[i]=y;
        if(!*active || power<gate || !std::isfinite(power))continue;
        bool train=*training_pos<training_len;
        C desired=train?training[(*training_pos)++]:C(y.real()>=0?.707f:-.707f,y.imag()>=0?.707f:-.707f);
        C error=desired-y;
        float step=(train?mu:dd_mu)/(eps+power);
        for(int k=0;k<taps;k++)weights[k]+=step*std::conj(error)*newest[-k];
        // Disable adaptation on catastrophic divergence; reacquire on next preamble.
        if(!std::isfinite(std::norm(y)) || std::norm(y)>1e6f) {*active=0;std::fill(weights,weights+taps,C(0,0));weights[0]=C(1,0);}
    }
}
