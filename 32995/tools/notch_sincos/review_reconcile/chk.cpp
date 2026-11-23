// check the review's test-blindness, branch-step and error-location claims
#include <initializer_list>
#include <cmath>
#include <cstdio>
#include "helper.inc"
static double ulpf(double y){ float a=fabs(y); return nextafterf(a,INFINITY)-a; }
int main(){
  // impulse response of the design with cos+e, against the exact design, at the test's A=0.1, Q=4
  double fs=8000,fc=5,A=0.1,Q=4,w=2*M_PI*fc/fs,s=sin(w),c=cos(w);
  auto ir=[&](double ce,double y[3],double&a1,double&a2){double al=s/(2*Q),i=1/(1+al),b0=(1+al*A*A)*i,b1=-2*ce*i,b2=(1-al*A*A)*i;a1=b1;a2=(1-al)*i;y[0]=b0;y[1]=b1-a1*y[0];y[2]=b2-a1*y[1]-a2*y[0];};
  double x[3],m[3],a1,a2; ir(c,x,a1,a2); ir(c+1e-5,m,a1,a2);
  double disc=a1*a1-4*a2, r=disc>0?(-a1+sqrt(disc))/2:sqrt(a2);
  printf("5 Hz/8 kHz, cos+1e-5: impulse output differences %.2e %.2e %.2e (test tolerance 3e-6); largest pole radius %.5f\n",fabs(m[0]-x[0]),fabs(m[1]-x[1]),fabs(m[2]-x[2]),r);
  // step across each branch boundary, as error of the difference against the true difference
  for (float b : {0.785398163f, 2.35619449f}) {
    float lo=(b==0.785398163f)?b:nextafterf(b,0.f), hi=nextafterf(lo,4.f), sl,cl,sh,ch;
    calculate_sinf_cosf(lo,sl,cl); calculate_sinf_cosf(hi,sh,ch);
    printf("branch at %.7f: step error sin %.2e cos %.2e\n",b,fabs((sh-sl)-(sin((double)hi)-sin((double)lo))),fabs((ch-cl)-(cos((double)hi)-cos((double)lo))));
  }
  // exhaustive 1e-4..pi: where the largest absolute and ulp errors are
  double es=0,eu=0,cs=0,cu=0,esa=0,eua=0,csa=0,cua=0; long n=0;
  for (float a=1e-4f; a<=3.14159274f; a=nextafterf(a,4.f)) { float sf,cf; calculate_sinf_cosf(a,sf,cf); double S=sin((double)a),C=cos((double)a);
    double e=fabs(sf-S),u=e/ulpf(S); if(e>es){es=e;esa=a;} if(u>eu){eu=u;eua=a;}
    e=fabs(cf-C);u=e/ulpf(C); if(fabs(C)>1e-3){ if(e>cs){cs=e;csa=a;} if(u>cu){cu=u;cua=a;} } n++; }
  printf("%ld floats. sin: max err %.2e at %.4f (%.2f ulp there), max %.2f ulp at %.4f\n",n,es,esa,es/ulpf(sin(esa)),eu,eua);
  printf("cos: max err %.2e at %.4f (%.2f ulp there), max %.2f ulp at %.4f\n",cs,csa,cs/ulpf(cos(csa)),cu,cua);
}
