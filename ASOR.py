import dispy, sys, math, time

def setup():
    import multiprocessing, multiprocessing.sharedctypes
    import ctypes
    global X, flags,token
    lock_flags = multiprocessing.Lock()
    lock_token = multiprocessing.Lock()
    MAX_NSIZE = 1000
# Shared memory among processes in each of the nodes
    X = multiprocessing.sharedctypes.RawArray(ctypes.c_double,MAX_NSIZE)
    flags = multiprocessing.sharedctypes.Array(ctypes.c_int,MAX_NSIZE, lock = lock_flags)
    token = multiprocessing.sharedctypes.Array(ctypes.c_int,1, lock = lock_token)
    token[0] = 0
    return 0

def cleanup():
    del globals()['X','flags','token']    

# 'compute' is distributed to each node running 'dispynode';
# runs on each processor in each of the nodes
def compute(start,end,nsize,index,job_num,matrix,R):
    import os, time,sys, numpy
    global X, flags,token
    l2norm = 0.0    # SUM((X_new - X_old)^2)
    ite = 0         #iteration in each of the nodes
    EPS = 1e-8      # convergence criteria
    compute_time = 0.0
    syn_time = 0.0
# Numpy initialization
    matrix_num = numpy.array(matrix).reshape(nsize,nsize)
    R_num = numpy.array(R).reshape(nsize,1)
    X_num = numpy.ctypeslib.as_array(X, shape = (1,nsize))
#if start>end then quit immediately
    if start > end:
        flags[index] = 1
        return [index,os.getpid()]

# kernel algorithm          
#numpy style
    while True:
        l2norm = 0.0
        ite += 1
        tmp_time = time.time()
        for i in range(start,end+1):
            old = X_num[i]      
            tmp = numpy.dot(X_num,matrix_num[i].reshape(nsize,1)) - matrix_num[i][i]*X_num[i]
            X_num[i] = 1.0/float(matrix_num[i][i])*(R_num[i]-tmp[0])
            l2norm += pow(old-X_num[i], 2)
        compute_time += time.time() - tmp_time   
        #tmp_time = time.time() 
        if l2norm < EPS:
            flags[index] = 1
        else:
            flags[index] = 0 
#Send provisional result to client
        if flags[index] == 1 and token[0] == index and sum(flags) == job_num :
            dispy_provisional_result((1,index,start,end,X[start:end+1],ite,compute_time,syn_time))
            token[0] = (token[0] + 1) % job_num    
            time.sleep(1)
        #syn_time += time.time() - tmp_time
    return  [os.getpid(),index,start,end,X_num[start:end+1],compute_time,syn_time]
    
def job_callback(job):
    import numpy,os
    global result,ready,job_num
    if job.status == dispy.DispyJob.ProvisionalResult:
#parse result
        ready[job.result[1]] = 1
        if sum(ready) != job_num:
            return 0
        local_ite[0] += 1
        result[job.result[2]:job.result[3]+1] = job.result[4] 
        ite[job.result[1]] = job.result[5] 
        compute_time[job.result[1]] = job.result[6] 
        syn_time[job.result[1]] = job.result[7] 
        
# numpy initialization
        matrix_num = numpy.array(matrix).reshape(nsize,nsize)
        R_num = numpy.array(R).reshape(nsize,1)
        X_num = numpy.array(result[0:nsize]).reshape(nsize,1)

# Run convergence test (numpy style)
        l2norm = 0.0
        for i in range(nsize):
            old = result[i]
            tmp = numpy.dot(matrix_num[i],X_num) - matrix_num[i][i]*X_num[i]
            fresh = 1.0/float(matrix_num[i][i])*(R_num[i]-tmp[0])
            err = pow(old-fresh, 2)
            if err >= EPS:
                return 0
            l2norm += err

        print '@@',job.result[1],l2norm,local_ite[0]
        if l2norm < EPS:    
            for j in jobs:
                if j.status in [dispy.DispyJob.Created, dispy.DispyJob.Running,
                                dispy.DispyJob.ProvisionalResult]:
                    cluster.cancel(j)
          


if __name__ == '__main__':
    argv = sys.argv
    if argv.__len__() != 3:
        print 'Usage: ASOR <#thread> <file path>'
        exit()
#globals
    global matrix, R, result, nsize, EPS, local_ite, ite, compute_time, ready,job_num
    
#Read matrix info and create RHS vector
    try:
        data = open(argv[2])
    except:
        print 'Cannot find file'
        exit()
    local_ite = [0]
    nsize = int(data.readline().split()[0])
    EPS = 1e-8
    done = 0
    matrix = [0 for n in range(nsize*nsize)]
    R = [ 0 for n in range(nsize)]
    result = [ 0 for n in range(nsize)]
   
    while not done :
        line = data.readline()
        if line == '' or line.split()[0] == '0':
            done = 1
        else:
            matrix[(int(line.split()[0])-1)*nsize+(int(line.split()[1])-1)] = float(line.split()[2]) 
    X_ = [n for n in range(1,nsize+1)]  
    for i in range(nsize) :
        for j in range(nsize) :
            R[i] += X_[j]*matrix[i*nsize+j]            

#init parameters
    job_num = int(argv[1])
    ready = [ 0 for n in range(job_num)]
    ite = [ 0 for n in range(job_num)]
    compute_time = [ 0 for n in range(job_num)]
    syn_time = [ 0 for n in range(job_num)]
    workload = int(math.ceil(float(nsize)/float(job_num)))
    
    print 'Finish reading file'
#Create job cluster
    cluster = dispy.JobCluster(compute,setup=setup,cleanup=cleanup,callback=job_callback)
      
#Assign jobs
    jobs = []
    for n in range(job_num):
        start = n*workload
        end = (n+1)*workload - 1
        if end >= nsize:
            end = nsize - 1
        job = cluster.submit(start,end,nsize,n,job_num,matrix,R)
        job.id = n
        jobs.append(job)
    ret = []
    cluster.wait()
    for job in jobs:
        ret = job()
    cluster.stats()
    output = open('ASOR_Result','w')
    for ss in result:
        output.write(str(ss)+'\n')
    print 'Results save to "ASOR_Result"'
    print '#Convergence Test:',local_ite[0]
    print '#Iteration on each node:',ite
    print 'Computation cost on each node:',compute_time
    print 'Syn cost on each node:',syn_time