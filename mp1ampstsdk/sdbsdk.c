#define _GNU_SOURCE             /* To get DN_* constants from <fcntl.h> */
#include <signal.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <termios.h>
#include <fcntl.h>
#include <inttypes.h>
#include <time.h>
#include <pthread.h>
#include <unistd.h> // for usleep
#include <math.h>
#include <sys/ioctl.h>
#include <sys/time.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/eventfd.h>
#include <sys/poll.h>
#include <regex.h>
#include <sched.h>
#include <assert.h>
#include <errno.h>
#include <error.h>

#define PY_SSIZE_T_CLEAN
//#include <python3.7/Python.h>
#include <Python.h>
#include "sdbsdk.h" 

/*** if is to be compiled on the MP1 board:  gcc -shared -o librpmsg_sdb_sdk.so -fPIC rpmsg_sdb_sdk.c  
    gcc -shared -o librpmsg_sdb_sdk.so -fPIC -I="/usr/include/python3.5m" rpmsg_sdb_sdk.c   ***/


/***   Definitions   ***/ 
#define RPMSG_SDB_IOCTL_SET_EFD _IOW('R', 0x00, struct rpmsg_sdb_ioctl_set_efd *)
#define RPMSG_SDB_IOCTL_GET_DATA_SIZE _IOWR('R', 0x01, struct rpmsg_sdb_ioctl_get_data_size *)

#define TIMEOUT 30


/***   Typedefs   ***/

typedef struct
{
    int bufferId, eventfd;
} rpmsg_sdb_ioctl_set_efd;

typedef struct
{
    int bufferId;
    uint32_t size;
} rpmsg_sdb_ioctl_get_data_size;

typedef enum {
  STATE_READY = 0,
  STATE_SAMPLING,
  STATE_EXITING,
} machine_state_t;


/***   Static glb variables   ***/

static int * efd;
static int mFdSdbRpmsg = -1;  
static struct pollfd * fds;
static void * (*mmappedData); 
static int32_t fMappedData = 0;
static pthread_t thread;
static machine_state_t mMachineState = STATE_READY;
static uint8_t mDdrBuffAwaited=0;
static int32_t mSampFreq_Hz = 4;
static int32_t mSampParmCount;
static uint32_t mNbCompData=0, mNbUncompData=0;
static size_t filesize = 0; // also sdb buff size
static uint32_t sdbnum = 0;

static rpmsg_sdb_ioctl_set_efd q_set_efd;

static buffer_ready_cb * notify_buffer_ready = NULL;

void register_buff_ready_cb(buffer_ready_cb * cbfunc)
{
	assert (cbfunc != NULL && notify_buffer_ready == NULL);
    printf("C func register_buff_ready_cb called\n");  
    notify_buffer_ready = cbfunc;
//    Py_XINCREF(notify_buffer_ready);      
}


void unregister_buff_ready_cb(buffer_ready_cb * cbfunc)
{
	assert (cbfunc != NULL && notify_buffer_ready == cbfunc && mMachineState != STATE_SAMPLING);
//	Py_XDECREF(notify_buffer_ready);  # FIXME ? not clear if ref cnt has to be managed ?
	notify_buffer_ready = NULL;
}

static int CreateSdbBuffers(unsigned int buff_size, unsigned int buff_num) 
{  
    char *filename = "/dev/rpmsg-sdb";
 
    filesize = buff_size;
    sdbnum = buff_num;
    efd = calloc(buff_num, sizeof(int));
    fds = calloc(buff_num, sizeof(struct pollfd));    
    mmappedData = calloc(buff_num, sizeof(void *));
    printf("DBG filesize:%d\n",(unsigned int)filesize);
    //Open file
    mFdSdbRpmsg = open(filename, O_RDWR);
    if (mFdSdbRpmsg == -1) {
        perror("CreateSdbBuffers failed to open file");
        free (mmappedData);
        free (fds);
        free (efd);
        return -1;
    }
    for (int i=0; i<sdbnum; i++){
        // Create the evenfd, and sent it to kernel driver, for notification of buffer full
        efd[i] = eventfd(0, 0);
        if (efd[i] == -1) {
            perror("CreateSdbBuffers failed to get eventfd");
            for (int n=0; n<i; n++){
                int rc = munmap(mmappedData[n], filesize);
                assert(rc == 0);
            }
	    sdbnum = 0;	    
            free (mmappedData);
            free (fds);
            free (efd);
            close (mFdSdbRpmsg);            
            return -1;
        }
        printf("\nForward efd info for buf%d with fd:%d and efd:%d\n",i,mFdSdbRpmsg,efd[i]);
        q_set_efd.bufferId = i;
        q_set_efd.eventfd = efd[i];
//        printf ("\nIOCTL RPMSG_SDB_IOCTL_SET_EFD: %d\n", RPMSG_SDB_IOCTL_SET_EFD);
        if(ioctl(mFdSdbRpmsg, RPMSG_SDB_IOCTL_SET_EFD, &q_set_efd) < 0){
            perror("CreateSdbBuffers failed to set efd");
            for (int n=0; n<i; n++){
                int rc = munmap(mmappedData[n], filesize);
                assert(rc == 0);
            }            
	    sdbnum = 0;
            free (mmappedData);
            free (fds);
            free (efd);
            close (mFdSdbRpmsg);            
            return -1;            
        }
        // watch eventfd for input
        fds[i].fd = efd[i];
        fds[i].events = POLLIN;
        mmappedData[i] = mmap(NULL,
                                filesize,
                                PROT_READ | PROT_WRITE,
                                MAP_PRIVATE,
                                mFdSdbRpmsg,
                                0);
/*** FIXME  ?msynk tb called to flush mem ? ***/
        if (mmappedData[i] == MAP_FAILED){
            perror("CreateSdbBuffers failed to mmap buffer");            
            for (int n=0; n<i; n++){
                int rc = munmap(mmappedData[n], filesize);
                assert(rc == 0);
            } 
            sdbnum = 0;	    
            free (mmappedData);
            free (fds);
            free (efd);
            close (mFdSdbRpmsg);            
            return -1;                        
        }
        printf("\nDBG mmappedData[%d]:%p\n", i, mmappedData[i]);        
        fMappedData = 1;
    }
    return 0;
}



static void sleep_ms(int milliseconds)
{
    usleep(milliseconds * 1000);
}
 

void *sdb_thread(void *arg)
{
    int ret, rc;
//    int8_t mesgOK = 1;
//    uint32_t length;
//    int32_t wsize;
    int buffIdx = 0;
//    char tmpStr[100];
    char buf[16];
    int ThRetVal;
    
    rpmsg_sdb_ioctl_get_data_size q_get_data_size;

    while (1) {
        if (mMachineState == STATE_SAMPLING) {
            // wait till at least one buffer becomes available
            ret = poll(fds, sdbnum, TIMEOUT * 1000);
            if (ret == -1)
                perror("poll()");
            else if (ret)
                printf("Data buffer is available now. ret: %d\n", ret);
            else if (ret == 0){
                printf("No buffer data within %d seconds.\n", TIMEOUT);
            }
            if (fds[mDdrBuffAwaited].revents & POLLIN) {
                rc = read(efd[mDdrBuffAwaited], buf, 16);
                if (!rc) {
/*** FIXME ?whath to do? exit thread and roll back everything? how to notify app? through callback with NULL args? ***/                     
                    printf("stdin closed\n");
                    return 0;
                }
                printf("Parent read %lu (0x%lx) (%s) from efd[%d]\n",
                        (unsigned long) buf, (unsigned long) buf, buf, mDdrBuffAwaited);
                /* Get buffer data size*/
                q_get_data_size.bufferId = mDdrBuffAwaited;

                if(ioctl(mFdSdbRpmsg, RPMSG_SDB_IOCTL_GET_DATA_SIZE, &q_get_data_size) < 0) {
/*** FIXME ?whath to do? exit thread and roll back everything? how to notify app? through callback with NULL args? ***/                                         
                    error(EXIT_FAILURE, errno, "Failed to get data size");
                }

                if (q_get_data_size.size) {
                    printf("buf[%d] size:%d\n", q_get_data_size.bufferId, q_get_data_size.size);
                    mNbCompData += q_get_data_size.size;

                    unsigned char* pCompData = (unsigned char*)mmappedData[mDdrBuffAwaited];
                    for (int i=0; i<q_get_data_size.size; i++) {
                        mNbUncompData += (1 + (*(pCompData+i) >> 5));
                    }
//                    printf("[%ld.%06ld] vitural_tty_thread data EVENT buffIdx=%d mNbCompData=%u mNbUncompData=%u mNbWrittenInFileData=%u\n", 
//                          (long int)tval_result.tv_sec, (long int)tval_result.tv_usec, buffIdx, mNbCompData, mNbUncompData, mNbWrittenInFileData);    
#define DBG                    
#ifdef DBG                   
                    pCompData[0] = 0x55;    // just for debug
                    pCompData[1] = 0xAA;  
#endif                    
                    if(notify_buffer_ready != NULL) {                    
                    	notify_buffer_ready(pCompData, q_get_data_size.size);     					                    
                    } else {
/*** FIXME ?whath to do? exit thread and roll back everything? how to notify app? through callback with NULL args? ***/                                             
                    	printf ("Error: Call register_buff_ready_cb() before StartSdbReceiver()");
                    }   			
                }
                else {
                    printf("sdb_thread => buf[%d] is empty\n", mDdrBuffAwaited);
                }
                mDdrBuffAwaited++;
                if (mDdrBuffAwaited > 2) {
                    mDdrBuffAwaited = 0;
                }
            } else if (mMachineState == STATE_SAMPLING) {
                printf("sdb_thread wrong buffer index ERROR, waiting buffIdx=%d", buffIdx);
            }
        } else if (mMachineState == STATE_EXITING) {
            pthread_exit(&ThRetVal);
            break;
        }
        sleep_ms(50);      // give time to system sched
    }
}  


int InitSdb(unsigned int buff_size, unsigned int buff_num)
{
    printf("C func InitSdb called, buff_size: %d buff_num: %d \n", buff_size, buff_num);       
    return CreateSdbBuffers(buff_size, buff_num);  
}

 
int InitSdbReceiver(void)
{
    mMachineState = STATE_READY;
    mSampFreq_Hz = 4;
    mSampParmCount = 0;
    
    printf("C func InitSdbReceiver called\n");        
    if (pthread_create( &thread, NULL, sdb_thread, NULL) != 0) {
        perror("sdb_thread creation fails\n");
        return -1;
    }
    return 0;
}

 
void StartSdbReceiver(void)
{
	mDdrBuffAwaited=0;
    mMachineState = STATE_SAMPLING;
} 
 
void StopSdbReceiver(void)
{
    mMachineState = STATE_READY;
}
 
int  DeInitSdbReceiver(void)
{
	int * pThRetVal;
    mMachineState = STATE_EXITING;
    pthread_join(thread, (void **)&pThRetVal);
    for (int i=0;i<sdbnum;i++){
        int rc = munmap(mmappedData[i], filesize);
        assert(rc == 0);
    }
    sdbnum = 0;
    close(mFdSdbRpmsg);
    fMappedData = 0;
    free (efd);
    free (fds);
    free (mmappedData);
    printf("Buffers successfully unmapped\n");    
    return 0;
} 
 
 
 

