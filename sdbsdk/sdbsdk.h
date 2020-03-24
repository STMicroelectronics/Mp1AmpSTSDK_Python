
typedef unsigned int buffer_ready_cb(char * buffer, unsigned int buffer_len);

extern void InitSdb(unsigned int, unsigned int);    
extern int  InitSdbReceiver(void);
extern void StartSdbReceiver(void);
extern void StopSdbReceiver(void);
extern int  DeInitSdbReceiver(void);
extern void register_buff_ready_cb(buffer_ready_cb *);
extern void unregister_buff_ready_cb(buffer_ready_cb *); 

