// reconcile the review's notch gain claims: libm and helper, both against the exact design
#include <cstring>
#include <cmath>
#include <complex>
#include <cstdio>
#include <random>
#include <vector>
#include <algorithm>
#include "helper.inc"
struct C { float b0,b1,b2,a1,a2; };
template<bool H> static C design(float fs,float fc,float A,float Q){
    float omega = 2.0*M_PI*fc/fs; float s,c;
    if (H) calculate_sinf_cosf(omega,s,c); else { s=sinf(omega); c=cosf(omega); }
    float alpha = s/(2*Q);
    float b0 = 1.0+alpha*(A*A), b1=-2.0*c, b2=1.0-alpha*(A*A), a1=b1, a2=1.0-alpha;
    const float i = 1.0/(1.0+alpha);
    return {b0*i,b1*i,b2*i,a1*i,a2*i};
}
static double gdb(double b0,double b1,double b2,double a1,double a2,double w){
    std::complex<double> z1=std::polar(1.0,-w), z2=z1*z1;
    return 20*log10(std::abs((b0+b1*z1+b2*z2)/(1.0+a1*z1+a2*z2)));
}
static double gc(const C&c,double w){return gdb(c.b0,c.b1,c.b2,c.a1,c.a2,w);}
static double gx(double fs,double fc,double A,double Q,double w){
    double o=2*M_PI*fc/fs,al=sin(o)/(2*Q),i=1/(1+al);
    return gdb((1+al*A*A)*i,-2*cos(o)*i,(1-al*A*A)*i,-2*cos(o)*i,(1-al)*i,w);
}
static double shift_hz(const C&c,double fs,double fc){ // null frequency the coefficients actually implement
    double ce=-(double)c.b1/((double)c.b0+(double)c.b2); return fs/(2*M_PI)*acos(ce)-fc; }
static double pct(std::vector<double>&v,double p){size_t k=std::min(v.size()-1,(size_t)(p*v.size()));std::nth_element(v.begin(),v.begin()+k,v.end());return v[k];}
struct R{const char*n;double fmin,fmaxr,amax,qmin,qmax;double fsmin;};
int main(){
  const float rates[]={400,1000,2000,3201,4000,8000};
  for (R r: {R{"typical (1-8k, 30Hz-.45fs, 15-40dB, Q1-11.7)",30,.45,40,1,11.7,1000},
             R{"high Q (1-8k, 5-200Hz, 15-60dB, Q20-100)",5,.45,60,20,100,1000},
             R{"extreme (.4-8k, 5Hz-.49fs, 15-60dB, Q1-20)",5,.49,60,1,20,400}}){
    std::mt19937_64 g(12345); std::uniform_real_distribution<double>u(0,1);
    const int N=3000000; std::vector<double> el,eh,sl,sh,bw; el.reserve(N);eh.reserve(N);sl.reserve(N);sh.reserve(N);bw.reserve(N);
    double dcmax=0,dbmax=0; long same=0,hw=0,lw=0,unst=0; const int K=14;
    for(int n=0;n<N;n++){
      float fs; do fs=rates[g()%6]; while(fs<r.fsmin);
      double fhi=std::min(r.fmaxr*fs, r.qmin>=20?200.0:1e9);
      float fc=exp(log(r.fmin)+u(g)*(log(fhi)-log(r.fmin)));
      float att=15+u(g)*(r.amax-15), Q=r.qmin+u(g)*(r.qmax-r.qmin), A=powf(10,-att/40.0f);
      C l=design<false>(fs,fc,A,Q), h=design<true>(fs,fc,A,Q);
      if(!memcmp(&l,&h,sizeof(C))) same++;
      if(fabsf(h.a2)>=1||fabsf(h.a1)>=1+h.a2) unst++;
      double w=2*M_PI*fc/fs, xc=gx(fs,fc,A,Q,w), lc=gc(l,w), hc=gc(h,w);
      double dl=fabs(lc-xc), dh=fabs(hc-xc); el.push_back(dl); eh.push_back(dh);
      if(dh>dl+1e-12)hw++; else if(dl>dh+1e-12)lw++;
      dcmax=std::max(dcmax,fabs(hc-lc));
      sl.push_back(fabs(shift_hz(l,fs,fc))); sh.push_back(fabs(shift_hz(h,fs,fc)));
      if(n%3==0) for(int k=0;k<K;k++) for(int s=-1;s<=1;s+=2){ double wo=w*(1+s*1e-5*(1<<k)); dbmax=std::max(dbmax,fabs(gc(h,wo)-gc(l,wo))); }
    }
    printf("\n%s, %d cases\n  bit-identical %.1f%%  unstable(helper) %ld\n",r.n,N,100.0*same/N,unst);
    printf("  centre gain error vs exact design, dB:   p99  p99.9  max\n");
    printf("    libm    %.4f %.4f %.3f\n",pct(el,.99),pct(el,.999),*std::max_element(el.begin(),el.end()));
    printf("    helper  %.4f %.4f %.3f\n",pct(eh,.99),pct(eh,.999),*std::max_element(eh.begin(),eh.end()));
    printf("  helper further from exact in %.1f%%, closer in %.1f%%\n",100.0*hw/N,100.0*lw/N);
    printf("  helper vs libm, max gain difference: centre %.2f dB, within 8%% %.2f dB\n",dcmax,dbmax);
    printf("  null frequency error, Hz:  p99.9  max\n    libm    %.5f %.5f\n    helper  %.5f %.5f\n",pct(sl,.999),*std::max_element(sl.begin(),sl.end()),pct(sh,.999),*std::max_element(sh.begin(),sh.end()));
  }
  // the specific inputs the reviewers reported
  struct T{const char*n;float fs,fc,att,Q;} ts[]={{"whole-1",8000,0x1.e3036ep+4f,40,10},{"whole-2",4000,0x1.77c342p+2f,0x1.c084aap+5f,0x1.6312e2p+3f},{"commit2",3201,20.3147f,60,20}};
  puts("");
  for(auto&t:ts){float A=powf(10,-t.att/40.0f);C l=design<false>(t.fs,t.fc,A,t.Q),h=design<true>(t.fs,t.fc,A,t.Q);double w=2*M_PI*t.fc/t.fs;
    printf("%-8s centre: exact %.2f libm %.2f helper %.2f dB; null shift libm %.5f helper %.5f Hz\n",t.n,gx(t.fs,t.fc,A,t.Q,w),gc(l,w),gc(h,w),shift_hz(l,t.fs,t.fc),shift_hz(h,t.fs,t.fc));}
  // codex: init(8000, 7.3626175, 0.036813088, 50) through calculate_A_and_Q
  {float fs=8000,fc=7.3626175f,bwh=0.036813088f,att=50;float A=powf(10,-att/40.0f);float oc=log2f(fc/(fc-bwh/2.0f))*2.0f;float Q=sqrtf(powf(2,oc))/(powf(2,oc)-1.0f);C l=design<false>(fs,fc,A,Q),h=design<true>(fs,fc,A,Q);double w=2*M_PI*fc/fs;
   printf("codex-1  Q %.1f centre: exact %.2f libm %.2f helper %.2f dB; null shift libm %.5f helper %.5f Hz\n",Q,gx(fs,fc,A,Q,w),gc(l,w),gc(h,w),shift_hz(l,fs,fc),shift_hz(h,fs,fc));}
  {float fs=8000,fc=64.941856f,A=powf(10,-50.0f/40.0f);float Q=98.749f;C l=design<false>(fs,fc,A,Q),h=design<true>(fs,fc,A,Q);double w=2*M_PI*fc/fs;
   printf("codex-2  Q %.1f centre: exact %.2f libm %.2f helper %.2f dB; null shift libm %.5f helper %.5f Hz\n",Q,gx(fs,fc,A,Q,w),gc(l,w),gc(h,w),shift_hz(l,fs,fc),shift_hz(h,fs,fc));}
}
