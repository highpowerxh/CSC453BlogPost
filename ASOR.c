/** Asynchronous Parallel SOR Implementation
 *
 *  Author: Xi Jin
 *  2014.09.29
 */

 
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/time.h>
#include <math.h>
#include <assert.h>
#include "pthread.h"
#include "hrtimer_x86.h"
#include "atomic_ops.h"
#include <sched.h>
#include <time.h>
#define mbarrier() __asm__ __volatile__("mfence": : :"memory") 
#define MAX_THREADS 24
/** 
Solving a linear system : AX=b (A is PSD matrix)

Algorithm:
Inputs: A, b, ω (relaxation factor), X (old value of X)
Output: X_

Choose an initial guess X to the solution
repeat until convergence

for i from 1 until n do
	tmp = 0
	X = X_;
	for j from 1 until n do
		if j < i then
 			tmp = tmp + a[i][j] X[j] 
		else if j>i
			tmp = tmp + a[i][j] X_[j] 
	end (j-loop)
 	X_[i] = (1 - ω)X_[i] + ω / a[i][i] (bi - tmp)
end (i-loop)
check if convergence is reached
end (repeat)

*/

//#define DEBUG

#define VERIFY  // Choose to print solution to file: "result"

/**	Solve the equation:
 *	matrix * X = R
 */

double **matrix,*R;
static volatile double *X;
int nsize = 0;
double w = 1.0;
double EPS = 1e-8;
static volatile int converge = 0;
int *iteration;
int thread_num;
static volatile int token;
static volatile int ite_converge;
static volatile double hrtimer_converge;

typedef struct 
{
	volatile unsigned long flag;
	volatile ticket_lock_t tlock;
	volatile unsigned long test;
	volatile double	l2norm;
}__attribute__((aligned(64))) cflag;

static volatile cflag *flags;
double * hrtimer_compute;

int GetCpuCount()
{
    return (int)sysconf(_SC_NPROCESSORS_ONLN);
}

double max(int length, double *input)
{
	double max = 0.0;
	assert(input[length-1]!=NULL);
	for(int i=0;i<length;i++)
	{
		if(input[i]>max)
			max = input[i];
	}
	return max;
}

double average(int length, double *input)
{
	double avg = 0.0;
	assert(input[length-1]!=NULL);
	for(int i=0;i<length;i++)
		avg += input[i];
	return (double)avg/(double)length;
}

void shuffle(int *array, size_t n)
{
    if (n > 1) 
    {
        size_t i;
        for (i = 0; i < n - 1; i++) 
        {
          size_t j = i + rand() / (RAND_MAX / (n - i) + 1);
          int t = array[j];
          array[j] = array[i];
          array[i] = t;
        }
    }
}

void sense_reverse_barrier(int tid)
{
    static volatile unsigned long count = 0;
    static volatile unsigned int sense = 0;
    static volatile unsigned int thread_sense[MAX_THREADS] = {0};

    thread_sense[tid] = !thread_sense[tid];
    if (fai(&count) == thread_num-1) {
        count = 0;
        sense = !sense;
    } else {
        while (sense != thread_sense[tid]);     /* spin */
    }
}

/* Initialize the matirx. */

int initMatrix(const char *fname)
{
    FILE *file;
    int l1, l2, l3;
    double d;
    int nsize;
    int i, j;
    char * ret;
    double *tmp;
    char buffer[1024];

    if ((file = fopen(fname, "r")) == NULL) {
	fprintf(stderr, "The matrix file open error\n");
        exit(-1);
    }
    
    /* Parse the first line to get the matrix size. */
    ret = fgets(buffer, 1024, file);
    sscanf(buffer, "%d %d %d", &l1, &l2, &l3);
    nsize = l1;
#ifdef DEBUG
    fprintf(stdout, "matrix size is %d\n", nsize);
#endif

    /* Initialize the space and set all elements to zero. */
    matrix = (double**)malloc(nsize*sizeof(double*));
    assert(matrix != NULL);
    tmp = (double*)malloc(nsize*nsize*sizeof(double));
    assert(tmp != NULL);    
    for (i = 0; i < nsize; i++) {
        matrix[i] = tmp;
        tmp = tmp + nsize;
    }
    for (i = 0; i < nsize; i++) {
        for (j = 0; j < nsize; j++) {
            matrix[i][j] = 0.0;
        }
    }

    /* Parse the rest of the input file to fill the matrix. */
    for (;;) {
	ret = fgets(buffer, 1024, file);
	sscanf(buffer, "%d %d %lf", &l1, &l2, &d);
	if (l1 == 0) break;  // add additonal line to the end mark "eof"

	matrix[l1-1][l2-1] = d;   //l1 row  l2 column  d value
#ifdef DEBUG
	fprintf(stdout, "row %d column %d of matrix is %e\n", l1-1, l2-1, matrix[l1-1][l2-1]);
#endif
    }

    fclose(file);
    return nsize;
}

void initRHS(int nsize)
{
    int i, j;
    double * tmp__ = (double*)malloc(nsize * sizeof(double));
    assert(tmp__ != NULL);
    for (i = 0; i < nsize; i++) {
	tmp__[i] = i+1;
    }
    R = (double*)calloc(nsize , sizeof(double));
    assert(R != NULL);
    for (i = 0; i < nsize; i++) {
	for (j = 0; j < nsize; j++) {
	    R[i] += matrix[i][j] * tmp__[j];
	}
    }
}

void initResult(int nsize)
{
    if (nsize == 0) {
	fprintf(stderr, "Matrix need to be initialized first\n");
        exit(-1);
    }
    int i;
    X = (double*)calloc(nsize , sizeof(double));
    assert(X != NULL);
    iteration = (int *)calloc(thread_num,sizeof(int));
    assert(iteration!=NULL);
    flags = (cflag *)calloc(thread_num,sizeof(cflag));
    assert(flags!=NULL);
    hrtimer_compute=(double *)calloc(thread_num,sizeof(double));
    assert(hrtimer_compute!=NULL);
}

void solve(int start, int end,int index, int test){

	int i,j,m;
	double tmp,old;
	double l2norm = 0.0;
	if(end>=nsize)
		end = nsize - 1;
	
	for(i=start;i<=end;i++){
		tmp = 0;	
		old = X[i];
		for(j=0;j<nsize;j++){
			if(j != i)   // use new value X[]
				tmp = tmp + matrix[i][j]*X[j];
		}
		X[i] = (1-w)*old+ w/matrix[i][i]*(R[i]-tmp);	
		l2norm += pow(old-X[i],2);	
	}
	if(l2norm < EPS)
		flags[index].flag = 1;
	else
		flags[index].flag = 0;
	if(test == 1)
		flags[index].l2norm = l2norm;
}

static void *
task(void *arg)
{
	int index = *((int *) arg);
    	cpu_set_t mask,get;
    	CPU_ZERO(&mask);
        CPU_SET(index, &mask);
	int i,j,k,loop,allone;
	double l2normtotal;
	int counter = 0;
	int workload = (int)ceil((double)nsize/(double)thread_num) ;
	int start = workload*(index);
	int end = (index + 1)*workload-1;
	double hrtimer_tmp;
	int *seq = (int *)malloc(thread_num*sizeof(int));
	for(i=0;i<thread_num;i++)
		seq[i] = i;
        if (pthread_setaffinity_np(pthread_self(), sizeof(mask), &mask) < 0) {
            fprintf(stderr, "set thread affinity failed\n");
        }

	sense_reverse_barrier(index);
	int ite = 0;
	while(converge==0)
	{
		ticket_acquire(&flags[index].tlock);
		if(flags[index].test == 1)
		{
			solve(start,end,index,1);
			flags[index].flag = 0;
			flags[index].test = 0;
			sense_reverse_barrier(index);
		}
		else
		{
			hrtimer_tmp = gethrtime_x86();
			ite ++;
			solve(start,end,index,0);
			hrtimer_compute[index] += gethrtime_x86() - hrtimer_tmp;
		}
		if(token == index && flags[index].flag == 1&&converge==0)
		{
			//observe all flags
			allone = 1;
			for(j=0;j<thread_num;j++)
			{
				allone = allone & flags[j].flag;
			}
			if(allone == 1)
			{
				ite_converge ++;
				shuffle(seq,thread_num);	
				for(i=0;i<thread_num;i++)
					if(seq[i] != index)
					{
						ticket_acquire(&flags[seq[i]].tlock);
						flags[seq[i]].test = 1;
						ticket_release(&flags[seq[i]].tlock);
					}					
				hrtimer_tmp = gethrtime_x86();
				solve(start,end,index,1);
				hrtimer_converge += gethrtime_x86() - hrtimer_tmp;
				sense_reverse_barrier(index);
				l2normtotal = 0.0;
				for(j=0;j<thread_num;j++)
				{
					l2normtotal += flags[j].l2norm;
				}
				if(l2normtotal < EPS)
				{
					converge = 1;
				}
				else
				{
					token = (token + 1) % thread_num;
				}
			}
		}
	 	ticket_release(&flags[index].tlock);	
      	}
      	printf ("#%d finished\n",index);
      	    
        CPU_ZERO(&get);
        if (pthread_getaffinity_np(pthread_self(), sizeof(get), &get) < 0) {
            fprintf(stderr, "get thread affinity failed\n");
        }
        for (j = 0; j < 24; j++) {
            if (CPU_ISSET(j, &get)) {
                printf("thread %d is running in processor %d sched_getcpu %d\n", index, j,sched_getcpu());
            }
        }
	return  new int(ite);
}


int main(int argc, char **argv){

	setbuf(stdout,0);
	int num = sysconf(_SC_NPROCESSORS_CONF);
    	printf("system has %d processor(s)\n", num);
    	cpu_set_t mask,get;
    	CPU_ZERO(&mask);
        CPU_SET(0, &mask);
	int i,j ;
	int ite = 0;
	ite_converge = 0;
	hrtimer_converge = 0.0;
	int retcode,allone;
	void *retval;
	double hrtimer_tmp,hrtime_start,hrtime_end,l2normtotal;
	if ( argc != 4) {printf("[usage] SOR <matrix> <thread> <w>\n"); return 0;}
    	
        if (pthread_setaffinity_np(pthread_self(), sizeof(mask), &mask) < 0) {
            fprintf(stderr, "set thread affinity failed\n");
        }
 	thread_num = atoi(argv[2]);
 	w = atof(argv[3]);
	nsize = initMatrix(argv[1]); 	
 	initRHS(nsize);
   	initResult(nsize);
   	int workload = (int)ceil((double)nsize/(double)thread_num) ;
   	pthread_t thread[thread_num];
	int *seq = (int *)malloc(thread_num*sizeof(int));
	for(i=0;i<thread_num;i++)
		seq[i] = i;
	shuffle(seq,thread_num);
   	for(j=1;j<thread_num;j++)
	{
		retcode = pthread_create(&thread[j], NULL, task, new int(j));
		if (retcode != 0)
			fprintf (stderr, "create thread failed %d\n", retcode);
	}
	sense_reverse_barrier(0);  // start at the same time
	hrtime_start = gethrtime_x86();
	printf("Finish reading file. Start computing...\n");
	while(converge == 0)
	{
		ticket_acquire(&flags[0].tlock);
		if(flags[0].test == 1)
		{
			solve(0,workload-1,0,1);
			flags[0].flag = 0;
			flags[0].test = 0;
			sense_reverse_barrier(0);
		}
		else
		{
			hrtimer_tmp = gethrtime_x86();
			ite ++;
			solve(0,workload-1,0,0);
			hrtimer_compute[0] += gethrtime_x86() - hrtimer_tmp;
		}
		if(token == 0 && flags[0].flag == 1&&converge==0)
		{
			//observe all flags
			allone = 1;
			for(j=0;j<thread_num;j++)
			{
				allone = allone & flags[j].flag;
			}
			if(allone == 1)
			{
				ite_converge ++;
				shuffle(seq,thread_num);	
				for(i=0;i<thread_num;i++)
					if(seq[i] != 0)
					{
						ticket_acquire(&flags[seq[i]].tlock);	
						flags[seq[i]].test = 1;
						ticket_release(&flags[seq[i]].tlock);	
					}	
				hrtimer_tmp = gethrtime_x86();
				solve(0,workload-1,0,1);
				hrtimer_converge += gethrtime_x86() - hrtimer_tmp;
				sense_reverse_barrier(0);
				l2normtotal = 0.0;
				for(j=0;j<thread_num;j++)
					l2normtotal += flags[j].l2norm;
				if(l2normtotal < EPS)
				{
					converge = 1;
				}
				else
				{
					token = (token + 1) % thread_num;
				}
			}
		}
		ticket_release(&flags[0].tlock);
      	}
      	printf ("#%d finished\n",0);
      	iteration[0] = ite;
	for(j=1;j<thread_num;j++)
	{
		retcode = pthread_join(thread[j], &retval);
		iteration[j] = *(int *)retval;
		if (retcode != 0)
			fprintf (stderr, "join failed %d\n", retcode);
	}
	hrtime_end = gethrtime_x86();
	CPU_ZERO(&get);
        if (pthread_getaffinity_np(pthread_self(), sizeof(get), &get) < 0) 
            fprintf(stderr, "get thread affinity failed\n");
        for (j = 0; j < 24; j++) 
            if (CPU_ISSET(j, &get)) 
                printf("thread %d is running in processor %d sched_getcpu %d\n", -1, j,sched_getcpu());
#ifdef VERIFY
  	FILE *res;
        res = fopen ("ASOR result", "w");
        for (i = 0; i < nsize; i++) {
            fprintf (res, "[%d] = %lf\n", i+1, X[i]);
        }			
#endif
	double total = hrtime_end-hrtime_start;
	printf("Total time:%.16lfs\n",total);
	printf("Computation time:%.16lfs\n",max(thread_num,hrtimer_compute));
	printf("Convergence time:%.16lfs\n",hrtimer_converge);
	printf("Syn time:%.16lfs\n",total-max(thread_num,hrtimer_compute)-hrtimer_converge);
	for(i=0;i<thread_num;i++)
		printf("Iteration[%d]: %d\t\tComputation time:%.16lfs\n",i,iteration[i],hrtimer_compute[i]);
	printf("#Converge iteration:%d\n",ite_converge);
	printf("sizeof(cflag) = %lu\n",sizeof(cflag));

	return 0;
}
