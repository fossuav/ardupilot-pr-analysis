#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
namespace L { 
#include "h_low.inc"
}
namespace N {
#include "h_nolow.inc"
}
struct C { float b0,b1,b2,a1,a2; };
template<int V> static C d(float fs,float fc,float A,float Q){ float omega=2.0*M_PI*fc/fs,s,c; if(V==0){s=sinf(omega);c=cosf(omega);} else if(V==1) L::calculate_sinf_cosf(omega,s,c); else N::calculate_sinf_cosf(omega,s,c); float al=s/(2*Q),b0=1.0+al*(A*A),b1=-2.0*c,b2=1.0-al*(A*A),a2=1.0-al,i=1.0/(1.0+al); return {b0*i,b1*i,b2*i,b1*i,a2*i}; }
C dl(float a,float b,float c,float e){return d<0>(a,b,c,e);} C dh(float a,float b,float c,float e){return d<1>(a,b,c,e);} C dn(float a,float b,float c,float e){return d<2>(a,b,c,e);}
