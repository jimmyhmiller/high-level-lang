/* N threads each read a file of ./features, at most K inside open/read/close at once (a gate that
   spins, K=0 for none), then do WORK*1000 steps of work on it: gated-open N K WORK. With 12
   threads and 40: no gate 104-117 ms, K=6 96, K=4 109, K=2 158: with every core busy an open is
   about twice as slow as with only the readers running, whatever the gate.
   cc -O2 -o gated-open gated-open.c */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <pthread.h>
#include <dirent.h>
#include <time.h>
#include <stdatomic.h>
#include <sched.h>
/* N threads each: open+read+close a file with at most K threads inside at once (a spin gate, no
   sleeping; K=0: no gate), then WORK microseconds-ish of work on it. */
static char **names; static int count, N, K, WORK; static atomic_int next_i, inside; static volatile long sink;
static void *work(void *arg){ char buf[8192]; char path[512];
  for(;;){ int i=atomic_fetch_add(&next_i,1); if(i>=count) break;
    snprintf(path,sizeof path,"features/%s",names[i]);
    if(K){ int spins=0; for(;;){ int c=atomic_load(&inside); if(c<K && atomic_compare_exchange_weak(&inside,&c,c+1)) break; if(++spins>4000){ sched_yield(); spins=0; } } }
    int fd=open(path,O_RDONLY|O_CLOEXEC); if(fd<0){perror(path);exit(1);} long n=read(fd,buf,sizeof buf); close(fd);
    if(K) atomic_fetch_sub(&inside,1);
    long h=0; for(int k=0;k<WORK*1000;k++) h=h*31+buf[k%(n>0?n:1)]; sink+=h; } return 0; }
static double now(){struct timespec ts;clock_gettime(CLOCK_MONOTONIC,&ts);return ts.tv_sec*1e3+ts.tv_nsec/1e6;}
int main(int argc,char**argv){ N=atoi(argv[1]); K=atoi(argv[2]); WORK=atoi(argv[3]);
  DIR*d=opendir("features"); struct dirent*e; names=malloc(sizeof(char*)*20000);
  while((e=readdir(d))) if(e->d_name[0]!='.') names[count++]=strdup(e->d_name);
  double t=now(); pthread_t th[64]; for(long i=0;i<N;i++) pthread_create(&th[i],0,work,0);
  for(int i=0;i<N;i++) pthread_join(th[i],0); printf("%.1f\n",now()-t); }
