#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
struct C { float b0,b1,b2,a1,a2; };
C dl(float,float,float,float); C dh(float,float,float,float); C dn(float,float,float,float);
int main(){ const double rs[]={1000,1600,2000,3201,4000,8000}; for(double fs:{1000.,1600.,3200.,8000.}){C h=dh(fs,fs/4,0.1f,4),n=dn(fs,fs/4,0.1f,4),l=dl(fs,fs/4,0.1f,4);printf("fs/4 at %.0f: b1 libm %.3e helper %.3e no LOW %.3e\n",fs,l.b1,h.b1,n.b1);}
 std::mt19937_64 r(5);std::uniform_real_distribution<double>u(0,1);const int N=20000000;long dh_=0,dn_=0;double sl=0,sh=0,sn=0,ml=0,mh=0,mn=0;
 for(int k=0;k<N;k++){float fs=rs[r()%6],fc=exp(log(5.0)+u(r)*(log(.49*fs)-log(5.0))),a=15+u(r)*45,Q=1+u(r)*19,A=powf(10,-a/40.0f);C l=dl(fs,fc,A,Q),h=dh(fs,fc,A,Q),n=dn(fs,fc,A,Q);if(memcmp(&l,&h,sizeof(C)))dh_++;if(memcmp(&l,&n,sizeof(C)))dn_++;double o=2*M_PI*fc/fs,x=-2*cos(o)/(1+sin(o)/(2*(double)Q)),el=fabs(l.b1-x),eh=fabs(h.b1-x),en=fabs(n.b1-x);sl+=el*el;sh+=eh*eh;sn+=en*en;ml=fmax(ml,el);mh=fmax(mh,eh);mn=fmax(mn,en);}
 printf("coefficient sets differing from glibc: helper %.1f%%, no LOW %.1f%%\nb1 error against exact, RMS / max: glibc %.3e / %.2e, helper %.3e / %.2e, no LOW %.3e / %.2e\n",100.*dh_/N,100.*dn_/N,sqrt(sl/N),ml,sqrt(sh/N),mh,sqrt(sn/N),mn);}
