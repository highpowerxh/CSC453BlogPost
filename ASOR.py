import dispy, sys, math, time, numpy

def setup():
    import multiprocessing, multiprocessing.sharedctypes
    import ctypes
    global X, flags,token,spinning,convergence
    lock_flags = multiprocessing.Lock()
    lock_token = multiprocessing.Lock()
    lock_spinning = multiprocessing.Lock()
    lock_convergence = multiprocessing.Lock()
    MAX_NSIZE = 1000
    MAX_NJOB = 24
# Shared memory among processes in each of the nodes
    X = multiprocessing.sharedctypes.RawArray(ctypes.c_double,MAX_NSIZE)
    flags = multiprocessing.sharedctypes.Array(ctypes.c_int,MAX_NSIZE, lock = lock_flags)
    spinning = multiprocessing.sharedctypes.Array(ctypes.c_int,MAX_NJOB, lock = lock_spinning)
    token = multiprocessing.sharedctypes.Array(ctypes.c_int,1, lock = lock_token)
    token[0] = 0
    convergence = multiprocessing.sharedctypes.Array(ctypes.c_int,2, lock = lock_convergence) #[0]=global converge flag [1] = num_ite
    return 0

# 'compute' is distributed to each node running 'dispynode';
# runs on each processor in each of the nodes
def compute(start,end,nsize,index,job_num,matrix,R):
    import os, time,sys, numpy
    global X, flags,token, spinning,convergence
    l2norm = 0.0    # SUM((X_new - X_old)^2)
    ite = 0         #iteration in each of the nodes
    EPS = 1e-5      # convergence criteria
    total_time = 0.0
    compute_time = 0.0
    syn_time = 0.0
    converge_time = 0.0
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
    tmp_total = time.time()
    while convergence[0] == 0:
        while spinning[index] == 1:
            pass
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
            tmp_converge = time.time()
            token[0] = (token[0] + 1) % job_num    
            for i in range(job_num):
                spinning[i] = 1
            while sum(spinning) != job_num:
                pass
        #global convergence test (break locality)
            l2norm = 0.0
            convergence[1] += 1
            for i in range(0,nsize):
                old = X_num[i]      
                tmp = numpy.dot(X_num,matrix_num[i].reshape(nsize,1)) - matrix_num[i][i]*X_num[i]
                X_num[i] = 1.0/float(matrix_num[i][i])*(R_num[i]-tmp[0])
                l2norm += pow(old-X_num[i], 2)
            if l2norm < EPS:
                convergence[0] = 1
                for i in range(job_num):
                    spinning[i] = 0
                total_time = time.time() - tmp_total
                converge_time += time.time() - tmp_converge
                return  [1,index,start,end,X[start:end+1],ite,compute_time,syn_time,convergence[1],total_time,converge_time,total_time-compute_time-converge_time]
            else:
                for i in range(job_num):
                    spinning[i] = 0
                    flags[i] = 0
            converge_time += time.time() - tmp_converge
            #dispy_provisional_result((1,index,start,end,X[start:end+1],ite,compute_time,syn_time,spinning[index]))
            #time.sleep(1)
                        
        #syn_time += time.time() - tmp_time
    total_time = time.time() - tmp_total
    return  [1,index,start,end,X[start:end+1],ite,compute_time,syn_time,convergence[1],total_time,converge_time,total_time-compute_time-converge_time]


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
    EPS = 1e-5
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
    print 'Finish reading file'
    X_ = numpy.array([n for n in range(1,nsize+1)]).reshape(nsize,1)
    matrix_ = numpy.array(matrix).reshape(nsize,nsize)
    R_ = numpy.dot(matrix_,X_).reshape(1,nsize)
    R = R_.tolist()
#init parameters
    job_num = int(argv[1])
    ready = [ 0 for n in range(job_num)]
    ite = [ 0 for n in range(job_num)]
    total_time = [ 0 for n in range(job_num)]
    compute_time = [ 0 for n in range(job_num)]
    convergence_time = [ 0 for n in range(job_num)]
    syn_time = [ 0 for n in range(job_num)]
    workload = int(math.ceil(float(nsize)/float(job_num)))
    
    print 'Finish creating matrix'
#Create job cluster
    cluster = dispy.JobCluster(compute,setup=setup)
      
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
        local_ite[0] = ret[8]
        ite[ret[1]] = ret[5] 
        result[ret[2]:ret[3]+1] = ret[4] 
        total_time[ret[1]] = ret[9]
        compute_time[ret[1]] = ret[6]
        convergence_time[ret[1]] = ret[10] 
        syn_time[ret[1]] = ret[11] 
    cluster.stats()
    output = open('ASOR_Result','w')
    for ss in result:
        output.write(str(ss)+'\n')
    print 'Results save to "ASOR_Result"'
    print 'Number of Global Convergence Test:',local_ite[0]
    print 'Number of Iteration on each node:',ite
    id = total_time.index(max(total_time))
    print 'Total time cost:',total_time[id]
    print 'Computation cost:',compute_time[id]
    print 'Global convergence test cost:',convergence_time[id]
    print 'Syn cost:',syn_time[id]