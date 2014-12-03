import dispy, sys, math, time

def setup():
    import multiprocessing, multiprocessing.sharedctypes
    import ctypes
    global X, flags
    lock_X = multiprocessing.Lock()
    lock_flags = multiprocessing.Lock()
    MAX_NSIZE = 1000
# Shared memory among processes in each of the nodes
    X = multiprocessing.sharedctypes.Array(ctypes.c_double,MAX_NSIZE, lock = lock_X)
    flags = multiprocessing.sharedctypes.Array(ctypes.c_int,MAX_NSIZE, lock = lock_flags)
    return 0

def cleanup():
    del globals()['X','flags']    

# 'compute' is distributed to each node running 'dispynode';
# runs on each processor in each of the nodes
def compute(start,end,nsize,index,job_num,matrix,R):
    import os, time,sys,numpy
    global X, flags
    l2norm = 0.0    # SUM((X_new - X_old)^2)
    ite = 0         #iteration in each of the nodes
    EPS = 1e-8      # convergence criteria
    compute_time = 0.0
# Numpy initialization
    matrix_num = numpy.array(matrix).reshape(nsize,nsize)
    R_num = numpy.array(R).reshape(nsize,1)

#if start>end then quit immediately
    if start > end:
        flags[index] = 1
        return [index,os.getpid()]
    
# observe all flags
    def allone(fa,job_num):
        ret = 0
        for i in range(job_num):
            ret += fa[i]
        if ret == job_num:
            return True
        else:
            return False
        
# kernel algorithm    

    while True:
        l2norm = 0.0
        ite += 1
        
#deprecated Old style         
        for i in range(start,end+1):
            tmp = 0
            old = X[i]
            tmp_time = time.time()
            for j in range(nsize):
                if i != j:
                    tmp += matrix[i*nsize+j]*X[j]
            compute_time += time.time() - tmp_time        
            X[i] = 1.0/float(matrix[i*nsize+i])*(R[i]-tmp)
            l2norm += pow(old-X[i], 2)
'''           
numpy style
        tmp_time = time.time()
        for i in range(start,end+1):
            X_num = numpy.array(X[0:nsize]).reshape(nsize,1) 
            old = X[i]
            tmp = numpy.dot(X[0:nsize],matrix_num[i].reshape(nsize,1)) - matrix_num[i][i]*X[i]
            X[i] = 1.0/float(matrix_num[i][i])*(R_num[i]-tmp[0])
            l2norm += pow(old-X[i], 2)
        compute_time += time.time() - tmp_time    
'''
        if l2norm < EPS:
            flags[index] = 1
        else:
            flags[index] = 0 
#Send provisional result to client
        if flags[index] == 1 and allone(flags,job_num):
            dispy_provisional_result((os.getpid(),index,start,end,X[start:end+1],ite,compute_time))  

    return  [os.getpid(),index,start,end,X[start:end+1],compute_time]
    
def job_callback(job):
    import numpy
    if job.status == dispy.DispyJob.ProvisionalResult:
#parse result
        result[job.result[2]:job.result[3]+1] = job.result[4] 
        ite[job.result[1]] = job.result[5] 
        compute_time[job.result[1]] = job.result[6] 
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
            l2norm += pow(old-fresh, 2)
        if l2norm < EPS:    
            for j in jobs:
                if j.status in [dispy.DispyJob.Created, dispy.DispyJob.Running,
                                dispy.DispyJob.ProvisionalResult]:
                    cluster.cancel(j)
        else:
            #print 'Just local Convergence'
            local_ite[0] += 1
            


if __name__ == '__main__':
    argv = sys.argv
    if argv.__len__() != 3:
        print 'Usage: ASOR <#thread> <file path>'
        exit()
#globals
    global matrix, R, result, nsize, EPS, local_ite, ite, compute_time
    
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
    ite = [ 0 for n in range(job_num)]
    compute_time = [ 0 for n in range(job_num)]
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

