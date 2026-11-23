// the round-three finding: poles at the edge of the unit circle just under Nyquist, libm against the helper
#include <cmath>
#include <initializer_list>
#include <cstdio>
struct C { float b0,b1,b2,a1,a2; };
C design_l(float,float,float,float); C design_h(float,float,float,float);
static bool unstable(const C&c){ double a1=c.a1,a2=c.a2; return fabs(a2)>=1 || fabs(a1)>=1+a2; }
int main(){ {C l=design_l(8000,nextafterf(4000,0),0.1f,0.5f),h=design_h(8000,nextafterf(4000,0),0.1f,0.5f);
  printf("reported input: libm a1 %.10f a2 %.10f unstable %d; helper a1 %.10f a2 %.10f unstable %d\n",l.a1,l.a2,unstable(l),h.a1,h.a2,unstable(h));}
 for(float lim:{0.5f,0.499f,0.495f,0.49f,0.48f}) for(float Q:{0.5f,1.0f,2.0f,4.0f}){ long n=0,ul=0,uh=0,only=0; for(float fs:{400.f,1000.f,1600.f,2000.f,3200.f,3201.f,4000.f,8000.f}){ float f=nextafterf(lim*fs,0.f); for(int k=0;k<200000;k++){ if(f>=0.5f*fs){f=nextafterf(f,0.f);continue;} C l=design_l(fs,f,0.1f,Q),h=design_h(fs,f,0.1f,Q); bool a=unstable(l),b=unstable(h); n++; ul+=a; uh+=b; only+=(b&&!a); f=nextafterf(f,0.f);} } if(ul||uh||lim==0.5f) printf("top %.3f of rate, Q %.1f: %ld notches, unstable with libm %ld, helper %ld, helper only %ld\n",lim,Q,n,ul,uh,only);}
}
