/* How fast N threads open, read and close every file of ./features (run in a fixture directory):
   open-threads N 0. On the machine this was written on (8 fast cores, 4 slow), 10,000 small files:
   1 thread 150-200 ms, 2: 85, 3: 62, 4: 50-58, 5-6: 80-98, 8: 100, 12: 121. More threads at once
   in open() make every open slower. cc -O2 -o open-threads open-threads.c */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <pthread.h>
#include <dirent.h>
#include <time.h>
#include <sys/stat.h>
#include <sys/resource.h>
static char **names; static int count, nthreads, mode;
static void *work(void *arg){ long t=(long)arg; char buf[8192]; char path[512];
  for(int i=t;i<count;i+=nthreads){ int fd;
    snprintf(path,sizeof path,"features/%s",names[i]);
    fd=open(path,O_RDONLY|O_CLOEXEC);
    if(fd<0){perror(path);exit(1);} 
    if(mode!=1) read(fd,buf,sizeof buf);
    if(mode==0) close(fd);} return 0; }
static double now(){struct timespec ts;clock_gettime(CLOCK_MONOTONIC,&ts);return ts.tv_sec*1e3+ts.tv_nsec/1e6;}
int main(int argc,char**argv){ nthreads=atoi(argv[1]); mode=atoi(argv[2]);
  struct rlimit rl={65536,65536}; setrlimit(RLIMIT_NOFILE,&rl);
  DIR*d=opendir("features"); struct dirent*e; names=malloc(sizeof(char*)*20000);
  while((e=readdir(d))) if(e->d_name[0]!='.') names[count++]=strdup(e->d_name);
  double t=now(); pthread_t th[64]; for(long i=0;i<nthreads;i++) pthread_create(&th[i],0,work,(void*)i);
  for(int i=0;i<nthreads;i++) pthread_join(th[i],0); printf("threads=%d mode=%d (0 open+read+close, 1 open only, 2 open+read): %.1f ms\n",nthreads,mode,now()-t); }
