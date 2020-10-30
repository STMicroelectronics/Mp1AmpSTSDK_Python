################################################################################
# COPYRIGHT(c) 2020 STMicroelectronics                                         #
#                                                                              #
# Redistribution and use in source and binary forms, with or without           #
# modification, are permitted provided that the following conditions are met:  #
#   1. Redistributions of source code must retain the above copyright notice,  #
#      this list of conditions and the following disclaimer.                   #
#   2. Redistributions in binary form must reproduce the above copyright       #
#      notice, this list of conditions and the following disclaimer in the     #
#      documentation and/or other materials provided with the distribution.    #
#   3. Neither the name of STMicroelectronics nor the names of its             #
#      contributors may be used to endorse or promote products derived from    #
#      this software without specific prior written permission.                #
#                                                                              #
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"  #
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE    #
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE   #
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE    #
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR          #
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF         #
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS     #
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN      #
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)      #
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE   #
# POSSIBILITY OF SUCH DAMAGE.                                                  #
################################################################################

import sys, argparse
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
from mp1ampstsdk.commsdk import CommAPIAnswersListener
from mp1ampstsdk.commsdk import CommAPINotificationsListener
from mp1ampstsdk.commsdk import CommAPI
from mp1ampstsdk.py_sdbsdk import RpmsgSdbAPI
from mp1ampstsdk.py_sdbsdk import RpmsgSdbAPIListener

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
# Two tests available:
# -- commsdk: testing the OpenAMP comunication API between A7-M4 in a/sync mode and ASCII/binary mode
#eg. python3 demo_commsdk.py commsdk /usr/local/Cube-M4-examples/STM32MP157C-DK2/Applications/OpenAMP/OpenAMP_TTY_echo/lib/firmware/OpenAMP_TTY_echo.elf
# -- sdbsdk: testing the Shared Data Buffer transfer API from M4 to A7 in async binary mode
#eg. python3 demo_commsdk.py sdbsdk /usr/local/Cube-M4-examples/STM32MP157C-DK2/Applications/la/lib/firmware/how2eldb03110.elf


def main(argv):     

    try:

        parser = argparse.ArgumentParser(description='Run a demo with associated M4 Fw.')
        parser.add_argument('demo', type=str, help='The demo to be run: <commsdk> or <sdbsdk> ')
        parser.add_argument('m4fw', type=str, help='The associated m4 fw to be run: <OpenAMP_TTY_echo.elf> or <how2eldb03110.elf>')

        args = parser.parse_args()
        print ('Input test is ', args.demo)
        print ('M4 fw file is ', args.m4fw)

        print ("Entering main Py")
        if (args.demo == "sdbsdk"):

            ser_obj = CommAPI("/dev/ttyRPMSG0",     \
                                None,               \
                                args.m4fw,          \
                                '\n',               \
                                True)            
            sdb_obj = RpmsgSdbAPI(None, True)  

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
            while (i < 30):     # let sys run for 15S and serial getting msgs from M4 if any
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

        elif (args.demo == "commsdk"):
        
            api_obj = CommAPI("/dev/ttyRPMSG0", \
                              "/dev/ttyRPMSG1", \
                                args.m4fw,      \
                                ';',            \
                                True)
            m4_answ_listener = M4_answ_listener()
            m4_ntfy_listener = M4_ntfy_listener()

            #while True:

            print ("\nBlocking cmd_get: Test blk; ...")                
            datard = api_obj.cmd_get("Test blk;", 0)
            print ("Returned: ",datard)

            print ("\nBlocking cmd_set (binar data): 01,02,03,00 ...") 
            datawr = b'\1\2\3\0'
            datard = api_obj.cmd_set(datawr, 0)
            print ("Returned: ",datard)

            evt_answ.clear()
            api_obj.add_answers_listener(m4_answ_listener)

            print ("\nNon blocking cmd_get: Test non blk 1; ...")                        
            if api_obj.cmd_get("Test non blk 1;", 2) == -1:
                print ("API Locked: retry!")
            evt_answ.wait()

	        # TODO ack the M4 FW to not answer this cmd allowing response timeout to expire
            evt_answ.clear()
            print ("\nNon blocking cmd_get: Test non blk 2; ... (with no answ from M4 so timed out)")
            if api_obj.cmd_get("Test non blk 2;", 2) == -1:
                print ("API Locked: retry!")        
            evt_answ.wait() 

	        # async notify test
            print ("\nAsync notify test ...")           
            evt_ntfy.clear()
            api_obj.add_notifications_listener(m4_ntfy_listener)
            print ("Enter in a separate shell: \"echo 'Test ntfy' > /dev/ttyRPMSG1\"")
            evt_ntfy.wait()

            print ("Exiting test ...")
            api_obj.remove_notifications_listener(m4_ntfy_listener)
            api_obj.remove_answers_listener(m4_answ_listener)

#            sys.exit(0)      
#            os._exit(0)

    except KeyboardInterrupt:
        try:	
            # Exiting.
            print('\nExiting...\n')
            sys.exit(0)
        except SystemExit:
            os._exit(0)

#    except BTLEDisconnectError as e:
    except () as e:
        logging.debug("\n====>>>EXCEPTION! ", + str(e))                


if __name__ == "__main__":
    main(sys.argv[1:])


