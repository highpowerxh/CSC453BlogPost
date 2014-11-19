#CS453 Final Project Proposal
Dispy : Python Framework for Distributed and Parallel Computing
##Group Members
Xi Jin & Hao Xu
## Introduction
`Dispy` is a Python framework for parallel execution of computations by distributing them across multiple processors in a single machine (SMP). It is implemented with `asyncoro`, which is an independent framework for asynchronous and concurrent programming with coroutines. Dispy itself is well suited for data parallel (SIMD) paradigm where a computation is evaluated with different (large) datasets independently with no communication among computation tasks. When there is some communications among workloads, we need asyncoro framework to help passing message. The asyncore is like a message passing model for communicating with client and other computation tasks.
## Motivation

Solving linear system is a classical problem in many areas. Our main purpose is to solve a linear system by using successive over-relaxation algorithm.
This algorithm is a converging iterative process which can be implemented into synchronous or asynchronous version. For linear system: <img src="http://chart.googleapis.com/chart?cht=tx&chl=Ax=b" style="border:none;">. Assume <img src="http://chart.googleapis.com/chart?cht=tx&chl=A" style="border:none;"> can be decomposed into a diagonal component <img src="http://chart.googleapis.com/chart?cht=tx&chl=D" style="border:none;">, and strictly lower and upper triangular components <img src="http://chart.googleapis.com/chart?cht=tx&chl=L" style="border:none;"> and <img src="http://chart.googleapis.com/chart?cht=tx&chl=U" style="border:none;">: <img src="http://chart.googleapis.com/chart?cht=tx&chl=A=D%2BL%2BU" style="border:none;">. 

The system of linear equations may be rewritten as:
<p align="center"><img src="http://chart.googleapis.com/chart?cht=tx&chl=(D%2B\omega L) \mathbf{x} = \omega \mathbf{b} - [\omega U %2B (\omega-1) D ] \mathbf{x}" style="border:none;"></p>

Then 
<p align="center"><img src="http://chart.googleapis.com/chart?cht=tx&chl=x^{(k%2B1)}_i  = {(1-\omega)x^{(k)}_i}%2B\frac{\omega}{a_{ii}} \left(b_i - \sum_{j%3Ci} a_{ij}x^{(k%2B1)}_j - \sum_{j%3Ei} a_{ij}x^{(k)}_j \right),\quad i=1,2,\ldots,n" style="border:none;"></p>

We now focus on asynchronous version in Python with the help of dispy and asyncoro. Also we would like to know how Python could be a concise language than C and what the performance difference between them is.
## First Step
Firstly, we will convert our existing C program to Python version using dispy framework to gain parallelism. Since communications are required during the computation stage, we also need to apply asyncoro framework in our program.

Then we can compare total number of lines, speedup, communication cost and other performance issues with original C program.

At the same time, we have to figure out how exactly dispy assigns the job, synchronize jobs and its internal mechanism. Additional, we will explore how to make some optimization in Python like aligning a data structure into exactly one or two cache line to avoid false sharing problem and how to reduce communication cost in Python (eg. apply high performance lock and barrier)

##Reference
[1] Dispy: http://dispy.sourceforge.net

[2] Asyncoro: http://asyncoro.sourceforge.net/

[3] Renato de Leone. Partially and totally asynchronous algorithms for linear complementarity problems. _Journal of optimization theory and applications_, 69(2):235–249, 1991.

[4] R De Leone and Olvi L Mangasarian. Asynchronous parallel successive overrelaxation for the symmetric linear complementarity problem. _Mathematical Programming_, 42(1-3):347–361, 1988.

[5] Olvi L Mangasarian. Solution of symmetric linear complementarity problems by iterative methods. _Journal of Optimization Theory and Applications_, 22(4):465–485, 1977.

[6] Olvi L Mangasarian and R De Leone. Parallel successive overrelaxation methods for symmetric linear complementarity problems and linear programs. _Journal of Optimization Theory and Applications_, 54(3):437–446, 1987.


```
# 'compute' is distributed to each node running 'dispynode';
# runs on each processor in each of the nodes
def compute(n):
    import time, socket
    time.sleep(n)
    host = socket.gethostname()
    return (host, n)

if __name__ == '__main__':
    import dispy, random
    cluster = dispy.JobCluster(compute)
    jobs = []
    for n in range(10):
        # run 'compute' with a random number between 5 and 10
        job = cluster.submit(random.randint(5,10))
        job.id = n
        jobs.append(job)
    # cluster.wait() # wait for all scheduled jobs to finish
    for job in jobs:
        host, n = job() # waits for job to finish and returns results
        print('%s executed job %s at %s with %s' % (host, job.id, job.start_time, n))
        # other fields of 'job' that may be useful:
        # print(job.stdout, job.stderr, job.exception, job.ip_addr, job.start_time, job.end_time)
    cluster.stats()
```
