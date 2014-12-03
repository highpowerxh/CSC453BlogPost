#CS453 Final Project Update
Dispy : Python Framework for Distributed and Parallel Computing
##Group Member
Xi Jin & Hao Xu
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
## Complete Code
Please see [here](https://github.com/highpowerxh/CSC453BlogPost/blob/master/ASOR.py)

Flow Chart:
![Alt text](Images/Flowchart.png "Flow Chart")

## Performance Testing
**Comparison with C is in progress**

Here is a screenshot of a single run:

![Alt text](Images/ASOR_test.jpg "Testing")

Note: We didn't find SMP support in Dispy as it described in their document. Actually, it provides an MPI-like parallelism, so data does not have better locality performance. The final comparsion will seem to be a little unfair for dispy since the C version is using pthread which has better memory locality. But dispy version has only about 150 lines of code after clean up compare to the 600 lines of C version.

We'll test dispy version on multipy machines if possible
