// worst gain difference between helper and libm, searched at the frequency where two offset nulls differ most: x(x+d)=A^4
#include <cmath>
#include <complex>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include <algorithm>
struct C { float b0,b1,b2,a1,a2; };
C design_l(float,float,float,float); C design_h(float,float,float,float);
static double g(const C&c,double w){std::complex<double> z1=std::polar(1.0,-w),z2=z1*z1;return 20*log10(std::abs(((double)c.b0+(double)c.b1*z1+(double)c.b2*z2)/(1.0+(double)c.a1*z1+(double)c.a2*z2)));}
static double wn(const C&c){return acos(-(double)c.b1/((double)c.b0+(double)c.b2));} // the numerator sets the null
static double pct(std::vector<double>&v,double p){size_t k=std::min(v.size()-1,(size_t)(p*v.size()));std::nth_element(v.begin(),v.begin()+k,v.end());return v[k];}
struct R{const char*n;double fmin,fr,amax,qmin,qmax,fsmin,fcap;};
int main(){ const float rates[]={400,1000,2000,3201,4000,8000};
 for(R r:{R{"typical",30,.45,40,1,11.7,1000,1e9},R{"high Q ",5,.45,60,20,100,1000,200},R{"extreme",5,.49,60,1,20,400,1e9}}){
  std::mt19937_64 rg(777);std::uniform_real_distribution<double>u(0,1);const int N=20000000;std::vector<double> d;d.reserve(N/4);double mx=0,mf=0,mq=0,ma=0,mr=0;long uns=0;
  for(int n=0;n<N;n++){float fs;do fs=rates[rg()%6];while(fs<r.fsmin);double hi=std::min(r.fr*fs,r.fcap);float fc=exp(log(r.fmin)+u(rg)*(log(hi)-log(r.fmin)));float att=15+u(rg)*(r.amax-15),Q=r.qmin+u(rg)*(r.qmax-r.qmin),A=powf(10,-att/40.0f);
   C l=design_l(fs,fc,A,Q),h=design_h(fs,fc,A,Q); if(fabsf(h.a2)>=1||fabsf(h.a1)>=1+h.a2)uns++; if(!memcmp(&l,&h,sizeof(C)))continue;
   double w=2*M_PI*fc/fs,x=0,w1=wn(l),w2=wn(h),aa=(double)A*A;x=fabs(g(h,w)-g(l,w));for(double c:{w1,w2})for(int k=-10;k<=10;k++){double o=aa*pow(2.0,k*0.5)/(2*Q);for(double t:{c,c+o,c-o})x=std::max(x,fabs(g(h,t)-g(l,t)));} if(n%4==0)d.push_back(x); if(x>mx){mx=x;mf=fc;mq=Q;ma=att;mr=fs;}}
  printf("%s: %d cases, unstable %ld; of differing sets (sampled %zu) p99 %.3f p99.9 %.3f dB; worst %.2f dB at fs %.0f fc %.3f att %.1f Q %.1f\n",r.n,N,uns,d.size(),pct(d,.99),pct(d,.999),mx,mr,mf,ma,mq);}
}
