/* R threads only read every file of ./features; W threads each take a file once it is read and
   do about 40 us of work on it: readers-and-workers R W. With 3 readers and 9 workers: 74-77 ms,
   where 12 threads each reading and working take 102-115 (gated-open 12 0 40).
   cc -O2 -o readers-and-workers readers-and-workers.c */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <pthread.h>
#include <dirent.h>
#include <time.h>
#include <sys/resource.h>
#include <stdatomic.h>
#include <sched.h>
/* R reader threads open+read+close every file into its own buffer; W worker threads take each
   file once it is read and do ~40us of work on it. Workers look for read files by index; a file
   not read yet is waited for by spinning with a yield. */
static char **names; static int count, R, W; static atomic_int next_read, next_work; static char (*bufs)[4096]; static atomic_int *lens;
static volatile long sink;
static void *reader(void *arg){ char path[512];
  for(;;){ int i=atomic_fetch_add(&next_read,1); if(i>=count) break;
    snprintf(path,sizeof path,"features/%s",names[i]); int fd=open(path,O_RDONLY|O_CLOEXEC); if(fd<0){perror(path);exit(1);}
    long n=read(fd,bufs[i],4096); close(fd); atomic_store(&lens[i],(int)(n>0?n:1)); } return 0; }
static void *worker(void *arg){
  for(;;){ int i=atomic_fetch_add(&next_work,1); if(i>=count) break; int n; int spins=0;
    while((n=atomic_load(&lens[i]))==0){ if(++spins>2000){ sched_yield(); spins=0; } }
    long h=0; for(int k=0;k<40000;k++) h=h*31+bufs[i][k%n]; sink+=h; } return 0; }
static double now(){struct timespec ts;clock_gettime(CLOCK_MONOTONIC,&ts);return ts.tv_sec*1e3+ts.tv_nsec/1e6;}
int main(int argc,char**argv){ R=atoi(argv[1]); W=atoi(argv[2]);
  DIR*d=opendir("features"); struct dirent*e; names=malloc(sizeof(char*)*20000);
  while((e=readdir(d))) if(e->d_name[0]!='.') names[count++]=strdup(e->d_name);
  bufs=malloc((size_t)count*4096); lens=calloc(count,sizeof(atomic_int));
  double t=now(); pthread_t th[64]; int k=0; for(long i=0;i<R;i++) pthread_create(&th[k++],0,reader,0); for(long i=0;i<W;i++) pthread_create(&th[k++],0,worker,0);
  for(int i=0;i<k;i++) pthread_join(th[i],0); printf("%.1f\n",now()-t); }
