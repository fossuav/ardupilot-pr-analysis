// the round-two cold finding, and the same class of notch: low centre, deep, ordinary Q
#include <cmath>
#include <complex>
#include <cstdio>
#include <cstring>
#include <random>
struct C { float b0,b1,b2,a1,a2; };
C design_l(float,float,float,float); C design_h(float,float,float,float);
static double g(const C&c,double w){std::complex<double> z1=std::polar(1.0,-w),z2=z1*z1;return 20*log10(std::abs(((double)c.b0+(double)c.b1*z1+(double)c.b2*z2)/(1.0+(double)c.a1*z1+(double)c.a2*z2)));}
static double gx(double fs,double fc,double A,double Q,double w){double o=2*M_PI*fc/fs,al=sin(o)/(2*Q),i=1/(1+al);C c;std::complex<double> z1=std::polar(1.0,-w),z2=z1*z1;return 20*log10(std::abs(((1+al*A*A)*i+(-2*cos(o)*i)*z1+((1-al*A*A)*i)*z2)/(1.0+(-2*cos(o)*i)*z1+((1-al)*i)*z2)));}
int main(){
 float fs=8000,fc=11.047224f,bw=5,att=50,A=powf(10,-att/40.0f),oc=log2f(fc/(fc-bw/2.0f))*2.0f,Q=sqrtf(powf(2,oc))/(powf(2,oc)-1.0f);
 C l=design_l(fs,fc,A,Q),h=design_h(fs,fc,A,Q);double w=2*M_PI*fc/fs;
 printf("reported input: Q %.2f, exact %.2f, libm %.2f, helper %.2f dB at the centre\n",Q,gx(fs,fc,A,Q,w),g(l,w),g(h,w));
 std::mt19937_64 r(99);std::uniform_real_distribution<double>u(0,1);long diff=0,hw=0,lw=0,big_h=0,big_l=0;const int N=20000000;
 for(int n=0;n<N;n++){float f=exp(log(5.0)+u(r)*(log(30.0)-log(5.0))),a=40+u(r)*20,q=1+u(r)*11,Aa=powf(10,-a/40.0f);float s=(n%2)?8000:4000;C L=design_l(s,f,Aa,q),H=design_h(s,f,Aa,q);if(!memcmp(&L,&H,sizeof(C)))continue;diff++;double t=2*M_PI*f/s,x=gx(s,f,Aa,q,t),el=fabs(g(L,t)-x),eh=fabs(g(H,t)-x);if(eh>el)hw++;else if(el>eh)lw++;if(eh>3)big_h++;if(el>3)big_l++;}
 printf("5-30 Hz, 40-60 dB, Q 1-12, 4-8 kHz: %ld of %d differ; helper further from exact in %ld, libm further in %ld; more than 3 dB from exact: helper %ld, libm %ld\n",diff,N,hw,lw,big_h,big_l);
}
