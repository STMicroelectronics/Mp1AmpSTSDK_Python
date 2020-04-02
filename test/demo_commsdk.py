import sys
import os

from abc import ABCMeta
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
import serial
from serial import SerialException
from serial import SerialTimeoutException
import time
from datetime import datetime
from threading import RLock
import threading  
from commsdk.commsdk import CommAPIAnswersListener
from commsdk.commsdk import CommAPINotificationsListener
from commsdk.commsdk import CommAPI
from commsdk.py_sdbsdk import RpmsgSdbAPI
from commsdk.py_sdbsdk import RpmsgSdbAPIListener
import ctypes

evt_ntfy = threading.Event()
evt_answ = threading.Event()

class M4_answ_listener (CommAPIAnswersListener):

    def on_M4_answer(self, msg):
        print("on_M4_answer: ", msg)
        if msg == "Timeout":
            pass
        evt_answ.set()


class M4_ntfy_listener (CommAPINotificationsListener):

	def on_M4_notify(self, msg):
		print("on_M4_notify: ", msg)
		evt_ntfy.set()


class M4_sdb_rx_listener (RpmsgSdbAPIListener):

    def on_M4_sdb_rx(self, sdb, sdb_len):
        print ("on_sdb_rx, len: ", sdb_len)
        print ("    on_sdb_rx, sdb[0]: ", sdb[0].hex())  # just for testing 
        print ("    on_sdb_rx, sdb[1]: ", sdb[1].hex())              

#========================================================
# MAIN APPLICATION

#
# Main application.
#
def main(argv):     

    try:
        print ("Entering main Py")

        ser_obj = CommAPI("/dev/ttyRPMSG0", None, "how2eldb03110.elf")            
        sdb_obj = RpmsgSdbAPI(None)  

        m4_sdb_listener = M4_sdb_rx_listener()
        sdb_obj.add_sdb_buffer_rx_listener(m4_sdb_listener)                   

        answ = ser_obj.cmd_set("r", 0)    # send run cmd to M4 FW, (wait blocking for answ)       
        print ("--->M4: ","r")
        while (answ.find("boot successful") == -1):
            answ = ser_obj.cmd_get(None, 0)        
            print ("<---M4: ", answ)   

        sdb_obj.init_sdb(1024*1024, 3)  # shared data buffers bufsize, bufnum

        answ = ser_obj.cmd_set("S002M", 0)  # send sampling freq cmd to M4 FW (wait blocking for answ)       
        while (len(answ) > 0):
            answ = ser_obj.cmd_get(None, 0)        
            print ("<---M4: ", answ)   
         
        sdb_obj.start_sdb_receiver();  # start the user side drv receiver thread, the on_M4_sdb_rx will be triggered by M4 when sdb is ready

     
        i=0
        while (i < 20):     # let sys run for 10S serial getting msgs from M4 if any
            time.sleep(0.5)                   
            i=i+1
            while (len(answ) > 0):
                answ = ser_obj.cmd_get(None, 0)        
                print ("<---M4: ", answ)   

        
        print("Stopping everything .....")
        answ = ser_obj.cmd_set("Exit", 0)    # send stop cmd to M4 FW, (wait blocking for answ) 
        while (len(answ) > 0):
            answ = ser_obj.cmd_get(None, 0)        
            print ("<---M4: ", answ)   
                      
        sdb_obj.stop_sdb_receiver();  # stop the sdb receiver thread (make it ready to start again)
        sdb_obj.deinit_sdb()    # exit the rx th, close open files and signals, unmap the sdb memory, stop the M4 FW         

        raise SystemExit      
        return
                 

#**********************************************   End sdb test   *****************************************************
        
        api_obj = CommAPI("/dev/ttyRPMSG0", \
                          "/dev/ttyRPMSG1", \
                          "OpenAMP_TTY_echo.elf" )   
        m4_answ_listener = M4_answ_listener() 
        m4_ntfy_listener = M4_ntfy_listener()


#        evt_answ.clear()
#        api_obj.add_answers_listener(m4_answ_listener)

#        with open('lena.jpg', rb) as file
#            finished = False
#            while (not finished)
#                datard = file.read (10000)
#                if datard != 10000
#                    finished =True
#                if api_obj.cmd_set(datard, 2) == -1:
#                    print ("API Locked: retry!")
#                evt_answ.wait()


        while True:

            print ("Blocking cmd_get ...")                
            datard = api_obj.cmd_get("Prova blk", 0)
            print ("Returned: ",datard)

            datawr = 123
            datard = api_obj.cmd_set(datawr, 0)
            print ("Returned: ",datard)

            while True:
                pass

            evt_answ.clear()
            api_obj.add_answers_listener(m4_answ_listener)

            print ("Non blocking cmd_get 1 ...")                        
            if api_obj.cmd_get("Prova non blk 1", 2) == -1:
                print ("API Locked: retry!")
            evt_answ.wait()

	# TODO ack the M4 FW to not answer this cmd allowing response timeout to expire
            evt_answ.clear()
            print ("Non blocking cmd_get 2 ...(with no answ from M4 so timed out)")   
            if api_obj.cmd_get("Prova non blk 2", 2) == -1:
                print ("API Locked: retry!")        
            evt_answ.wait() 

	# async notify test
            evt_ntfy.clear()
            api_obj.add_notifications_listener(m4_ntfy_listener)
            print ("Enter in a separate shell: echo Prova ntfy > /dev/ttyRPMSG1 ")
            evt_ntfy.wait()

            print ("Exiting test")
            api_obj.remove_notifications_listener(m4_ntfy_listener)
            api_obj.remove_answers_listener(m4_answ_listener)

# TODO stop M4 FW
        sys.exit(0)      
        os._exit(0)

    except KeyboardInterrupt:
        try:	
            # Exiting.
            print('\nExiting...\n')
            sys.exit(0)
        except SystemExit:
            os._exit(0)

#    except BTLEDisconnectError as e:
    except () as e:
        logging.debug("\n====>>>EXCEPTION!!!! Ble Node Disconnected", + str(e))                


if __name__ == "__main__":
    main(sys.argv[1:])


