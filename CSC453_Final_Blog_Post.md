#CS453 Final Project Report
Dispy : Python Framework for Distributed and Parallel Computing
##Group Member
Xi Jin & Hao Xu
##Table of Contents

- [Introduction](#introduction)
- [Motivation](#motivation)
- [Challenge](#challenge)
- [Installation and Components Introduction](#installation-and-components-introduction)
- [Framework](#framework)
- [Algorithm](#algorithm)
- [Complete Code](#complete-code)
- [Performance Test](#performance-test)
- [Summary](#summary)
    - [cons:](#cons)
    - [pros:](#pros)
- [Reference](#reference)

## Introduction
`Dispy` is a Python framework for parallel execution of computations by distributing them across multiple processors in a single machine (SMP). It is implemented with asyncoro, which is an independent framework for asynchronous and concurrent programming with coroutines. Dispy itself is well suited for data parallel (SIMD) paradigm where a computation is evaluated with different (large) datasets independently with no communication among computation tasks. When there is some communications among workloads, we need asyncoro framework to help passing message. The asyncore is like a message passing model for communicating with client and other computation tasks.

`asyncoro` is a Python framework for asynchronous, concurrent, distributed programming using generator functions, asynchronous completions and message passing. asyncoro API can be used to create coroutines with generator functions, similar to the way threads are created with functions with Python’s threading module. Thus, programs developed with asyncoro have same logic and structure as programs with threads, except for a few syntactic changes - mostly using yield with asynchronous completions that give control to asyncoro’s scheduler, which interleaves executions of generators, similar to the way an operating system executes multiple processes.

`NumPy` is the fundamental package for scientific computing with Python. It contains among other things:
- a powerful N-dimensional array object
- sophisticated (broadcasting) functions
- tools for integrating C/C++ and Fortran code
- useful linear algebra, Fourier transform, and random number capabilities

Besides its obvious scientific uses, NumPy can also be used as an efficient multi-dimensional container of generic data. Arbitrary data-types can be defined. This allows NumPy to seamlessly and speedily integrate with a wide variety of databases.
## Motivation

Solving linear system is a classical problem in many areas. Our main purpose is to solve a linear system by using successive over-relaxation algorithm.
This algorithm is a converging iterative process which can be implemented into synchronous or asynchronous version. For linear system: <img src="http://chart.googleapis.com/chart?cht=tx&chl=Ax=b" style="border:none;">. Assume <img src="http://chart.googleapis.com/chart?cht=tx&chl=A" style="border:none;"> can be decomposed into a diagonal component <img src="http://chart.googleapis.com/chart?cht=tx&chl=D" style="border:none;">, and strictly lower and upper triangular components <img src="http://chart.googleapis.com/chart?cht=tx&chl=L" style="border:none;"> and <img src="http://chart.googleapis.com/chart?cht=tx&chl=U" style="border:none;">: <img src="http://chart.googleapis.com/chart?cht=tx&chl=A=D%2BL%2BU" style="border:none;">. 

The system of linear equations may be rewritten as:
<p align="center"><img src="http://chart.googleapis.com/chart?cht=tx&chl=(D%2B\omega L) \mathbf{x} = \omega \mathbf{b} - [\omega U %2B (\omega-1) D ] \mathbf{x}" style="border:none;"></p>

Then 
<p align="center"><img src="http://chart.googleapis.com/chart?cht=tx&chl=x^{(k%2B1)}_i  = {(1-\omega)x^{(k)}_i}%2B\frac{\omega}{a_{ii}} \left(b_i - \sum_{j%3Ci} a_{ij}x^{(k%2B1)}_j - \sum_{j%3Ei} a_{ij}x^{(k)}_j \right),\quad i=1,2,\ldots,n" style="border:none;"></p>

It proved to be always converged if the matrix is positive semi-definite.
The synchronous version requires all processes stop and share result at the end of each iteration. It gains benefit of running minimum number of iteration and being easy to control but suffers from high communication cost.

Alternatively, we can build asynchronous version that all processes keep running on their own workload. An observer will check if the global converge point is reached and tell all processes to stop. This method will reduce synchronous cost to minimum but it increases the number of iteration to finish the job.

We now focus on asynchronous version in Python with the help of dispy and asyncoro. Dispy is an ideal platform for our problem because it has a major feature that workers can send back provisional result while they can continue running and the client will decide to accept these sub-optimized result. Another intereting point is that numpy computation is much faster than normal operation and we wish to import it in our program. Also we would like to know how Python could be a concise language than C and what the performance difference between them is.
##Challenge
As the number of thread/process increasing, one major problem is that there will be more cache invalidation and writeback inside memory system. It will add latency to computation. Also the machine we use is node2x12x1a which is AMD OPTERON 12 core X2, two sockets, four memory controller machine, the socket to socket latency cannot be ignored. 
## Installation and Components Introduction
Since we use Python 2.7.8 in this project. We can install Dispy with:
```Bash
pip install dispy
```
Dispy consists of 4 components:

_dispy_ (client) provides two ways of creating “clusters”: JobCluster() when only one instance of dispy may run and SharedJobCluster() when multiple instances may run (in separate processes). If JobCluster() is used, the job scheduler is included in it will distribute jobs on the server nodes; if SharedJobCluster() is used, a separate scheduler (dispyscheduler) must be running.

_dispynode_ executes jobs on behalf of dispy. dispynode must be running on each of the (server) nodes that form the cluster.

_dispyscheduler_ is needed only when SharedJobCluster() is used; this provides a scheduler that can be shared by multiple dispy clients simultaneously.

_dispynetrelay_ is needed when nodes are located across different networks. If all nodes are on local network or if all remote nodes can be listed in ‘nodes’ parameter when creating cluster, there is no need for dispynetrelay - the scheduler can discover such nodes automatically. However, if there are many nodes on remote network(s), dispynetrelay can be used to relay information about the nodes on that network to scheduler, without having to list all nodes in ‘nodes’ parameter.
## Framework
Set up global variables and preprocess the data
```Python
def setup():
    pass
```
Clean up global variables, close file and etc.
```Python
def cleanup():
    pass
```
Function running on the laborers
```Python
def compute(#parameters from client#):
    return  0
```
When a job’s results become available, dispy will call provided callback function with that job as the argument. If a job sends provisional results with ‘dispy_provisional_result’ multiple times, then dispy will call provided callback each such time.

The (provisional) results of computation can be retrieved with ‘result’ field of job, etc. While computations are run on nodes in isolated environments, callbacks are run in the context of user programs from which (Shared) JobCluster is called - for example, callbacks can access global variables in programs that created cluster(s).

The interesting part here is we can check if this intermediate result satisfies the client. If it does, the client can stop all the jobs.
```Python
# When laborers send dispy_provisional_result back to client, client will run this function     
def job_callback(job):
    if job.status == dispy.DispyJob.ProvisionalResult:
        if "meet criteria (results satisfy client)":    
            for j in jobs:
                if j.status in [dispy.DispyJob.Created, dispy.DispyJob.Running,
                                dispy.DispyJob.ProvisionalResult]:
                    cluster.cancel(j) #then stop all the jobs
```
```Python
# running on client
if __name__ == '__main__':
# Create job cluster
    cluster = dispy.JobCluster(compute,setup=setup,cleanup=cleanup,callback=job_callback)
# Assign jobs
    job_num = 10
    jobs = []
    for n in range(job_num):
        job = cluster.submit(#parameters pass to laborers#)
        job.id = n
        jobs.append(job)
    cluster.wait() # waiting for all jobs done
    for job in jobs:
        job()
    cluster.stats()
```
##Algorithm
```
Solving a linear system : AX=b (A is PSD matrix)
Algorithm:
Inputs: A, b, ω (relaxation factor), X
Choose an initial guess X to the solution
repeat until convergence
for i from 1 until n do
	tmp = 0
	old= X[i];
	for j from 1 until n do
		if j != i then
 			tmp = tmp + a[i][j] X[j] // numpy function applied here to gain efficiency
	end (j-loop)
 	X[i] = (1 - ω)*old+ ω / a[i][i] (bi - tmp)
end (i-loop)
check if convergence is reached
end (repeat)
```
## Complete Code
Please see
[C Version](https://github.com/highpowerxh/CSC453BlogPost/blob/master/ASOR.c),
[Python Version](https://github.com/highpowerxh/CSC453BlogPost/blob/master/ASOR.py) (Updated, [Older Version](https://github.com/highpowerxh/CSC453BlogPost/blob/8bda86c02275174d734b0b35c4dc378102e4a54e/ASOR.py))

System Design Chart (Updated, [Older Version](Images/Flowchart.png)):

![Alt text](Images/systemchart.png "System Design Chart")

## Performance Test
Testing Platform

|   Node Name   |        CPU       |                Details               |Memory|
|:-------------:|:----------------:|:------------------------------------:|:----:|
|  node2x12x1a  |2 AMD Opteron 6172|Opteron, 2.1GHz, 12-Cores x 1-"Thread"| 16GB |
<a href="http://jsfiddle.net/xxfmh4hk/3/embedded/result/" target="_blank">![Alt text](Images/chart1k.png "Click to interact")</a>
<a href="http://jsfiddle.net/83w7ytrz/2/embedded/result/" target="_blank">![Alt text](Images/speedup1k.png "Click to interact")</a>
<a href="http://jsfiddle.net/qt9ot5s2/1/embedded/result/" target="_blank">![Alt text](Images/chart2k.png "Click to interact")</a>
<a href="http://jsfiddle.net/urb53j1v/2/embedded/result/" target="_blank">![Alt text](Images/speedup2k.png "Click to interact")</a>
<a href="http://jsfiddle.net/7s6s9cxc/1/embedded/result/" target="_blank">![Alt text](Images/chart3k.png "Click to interact")</a>
<a href="http://jsfiddle.net/cjfo45qL/1/embedded/result/" target="_blank">![Alt text](Images/speedup3k.png "Click to interact")</a>
Note: We didn't find SMP support in Dispy as it described in their document. Actually, it provides an MPI-like parallelism, so data does not have better locality performance. The final comparsion will seem to be a little unfair for dispy since the C version is using pthread which has better memory locality. But dispy version has only about 170 lines of code after clean up compare to the 470 lines of C version.
##Summary
Unfortunately, dispy didn't performance quite well as we expect.
###Cons:
1. Dispy is memory passing model among processes. Unlike share memory model, in order to share result vector X, the program actually calls pipe() using asyn socket communication. That's why we observe the speedup is quite linear within 10 processes but decreases dramatically after that. Also Python version even runs faster than C version with the 1000x1000 matrix test file but suffers from memory passing latency when dealing with large file.

2. Dispy didn't support large file input. we have tried 5000x5000 matrix but failed. The reason is that if client doesn't send that huge chunk of initialized data to workers, workers will throw timeout error.

3. Dispy's sending provisional result method is terrible. There is no blocking-style handler and worker won't know if their request was handled or waits on the queue so if we send result frequently, the client will die. That's the reason we give up old version.

###Pros:
1. Numpy works well and even beat C version with the 1000x1000 matrix

2. Python version only need less than half of the code comparing to C version

3. Program can be distributed to all CPU on network.

##Reference
[1] Dispy: http://dispy.sourceforge.net

[2] Asyncoro: http://asyncoro.sourceforge.net/

[3] Renato de Leone. Partially and totally asynchronous algorithms for linear complementarity problems. _Journal of optimization theory and applications_, 69(2):235–249, 1991.

[4] R De Leone and Olvi L Mangasarian. Asynchronous parallel successive overrelaxation for the symmetric linear complementarity problem. _Mathematical Programming_, 42(1-3):347–361, 1988.

[5] Olvi L Mangasarian. Solution of symmetric linear complementarity problems by iterative methods. _Journal of Optimization Theory and Applications_, 22(4):465–485, 1977.

[6] Olvi L Mangasarian and R De Leone. Parallel successive overrelaxation methods for symmetric linear complementarity problems and linear programs. _Journal of Optimization Theory and Applications_, 54(3):437–446, 1987.
