// built with the ChibiOS arithmetic: -fsingle-precision-constant
#include <cmath>
#include "helper.inc"
struct C { float b0,b1,b2,a1,a2; };
template<bool H> static C d(float fs,float fc,float A,float Q){
    float omega = 2.0*M_PI*fc/fs; float s,c;
    if (H) calculate_sinf_cosf(omega,s,c); else { s=sinf(omega); c=cosf(omega); }
    float alpha = s/(2*Q);
    float b0 = 1.0+alpha*(A*A), b1=-2.0*c, b2=1.0-alpha*(A*A), a1=b1, a2=1.0-alpha;
    const float i = 1.0/(1.0+alpha);
    return {b0*i,b1*i,b2*i,a1*i,a2*i};
}
C design_l(float fs,float fc,float A,float Q){return d<false>(fs,fc,A,Q);}
C design_h(float fs,float fc,float A,float Q){return d<true>(fs,fc,A,Q);}
