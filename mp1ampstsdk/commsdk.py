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


"""commsdk
The commsdk module is responsible for managing the A7-M4 communication through 
the OpenAMP RpMsg virtual COM port, and allocating the needed resources.
"""


# IMPORT

from abc import ABCMeta
from abc import abstractmethod
from serial import SerialException
from serial import SerialTimeoutException
from mp1ampstsdk.comm_exceptions import CommsdkInvalidOperationException
import serial
import threading  
import os
import sys
import time
import shutil


# CONSTANTS

"""Serial msgs terminator character."""
DFT_TERMINATOR = ';'
BINARY_ANSW_MAX_LEN = 512


# CLASSES

class ThM4Answers(threading.Thread):

    def __init__(self, caller, name=None, terminator=DFT_TERMINATOR, verbose=False):
        super().__init__(name=name)   
        self._caller = caller
        self._terminator = terminator
        self._verbose = verbose


    def run(self):

        try:

            if self._verbose:
                print ('Starting: ', self.name)
            self._answer = self._caller._serial_port_cmd.read_until(self._terminator,None)
            # if self._verbose:
            #    print ("RX:", self._answer.decode('utf-8'))
            if self._caller._answers_listener:
                if self._answer.decode('utf-8') is '' :  # TODO command timeout: generate ad-hoc msg 
                    self._answer = "Timeout".encode('utf-8')
                self._caller._answers_listener.on_M4_answer(self._answer.decode('utf-8'))                    
            else:
                raise CommsdkInvalidOperationException ("\nError amswers listener to be added")                
            self._caller._lock_cmd.release()       

        except (SerialException, SerialTimeoutException, CommsdkInvalidOperationException) as e:
            if self._caller._answers_listener.is_open:
                self._caller._answers_listener.close()
            self._caller._answers_listener = None            
            raise e


    def __del__(self):
        if self._verbose:
            print ("Deleting ThM4Answers")


class ThM4Notifications(threading.Thread):

    def __init__(self, caller, name=None, terminator=DFT_TERMINATOR, verbose=False):
        super().__init__(name=name)   
        self._caller = caller
        self._evt_stop_ntf = threading.Event()
        self._evt_stop_ntf.clear()
        self._terminator = terminator
        self._verbose = verbose


    def run(self):

        try:
            if self._verbose:
                print ('Starting: ', self.name)
            # Enabling spontaneous notifications by writing the OpenAMP rpmsg port at least one time with a non-null 
            # character. See email from MCD:
            # Yes this is a “normal” behavior.
            # For the RPMSG protocol both side have to know the remote destination address to send a message
            # So on M4 boot
            # M4 send a name service announcement RPMsg on Virtual UART init ( linked to the endpoint creation)
            # Here the M4 provides to the A7 its endpoint address ( 0x0) by sending the message to a specific address (0x35)
            # Alternate 1)
            # The M4 start to send new message 
            # As OpenAMP does not know the destination address => FAIL
            # Alternate 2)
            # The A7 send a first message
            # The A7 provide is address( 0x400) as source of the message to the M4 address 0x0
            # The OpenAMP associates both address and know now the A7 destination address
            # SUCCESS
            # This is the current implementation of the RPMSG protocol, so yes the A7 as to send the first message to finalize the connection.
            # https://wiki.st.com/stm32mpu/wiki/Coprocessor_management_troubleshooting_grid
#            self._caller._serial_port_ntf.write(self._terminator)
#            ret = self._caller._serial_port_ntf.read_until(self._terminator, None)   # wait 0.2 Sec for spurious echo if any                
#            self._caller._serial_port_ntf.flush() 

            while True:
                if self._evt_stop_ntf.isSet():
                    self._evt_stop_ntf.clear() 
                    if self._verbose:
                        print ("Stopping ThM4Notifications")
                    return
                self._ntf = self._caller._serial_port_ntf.read_until(self._terminator, None)
                if self._verbose and self._ntf.decode('utf-8') is not '':
                    print ("Rx Notif:", self._ntf.decode('utf-8'))
                if self._ntf.decode('utf-8') is not '':
                    if self._caller._notifications_listener:
                        self._caller._notifications_listener.on_M4_notify(self._ntf.decode('utf-8'))
                    else:
                        raise CommsdkInvalidOperationException ("\nError notification listener to be added")

        except (SerialException, SerialTimeoutException, CommsdkInvalidOperationException) as e:
            if self._caller._serial_port_ntf.is_open:
                self._caller._serial_port_ntf.close()
            self._caller._notifications_listener = None            
            raise e


    def join(self, timeout=None):
        
        if self._verbose:
            print ("Joining ThM4Notifications")
        self._evt_stop_ntf.set()
        super().join(timeout) 


    def __del__(self):
        if self._verbose:
            print ("Deleting ThM4Notifications")


class CommAPI():
    """CommAPI class.
    This class manages the communication via OpenAMP serial Rpmsg between the A7 and the M4.
    """

    def __init__(self, serial_port_cmd, serial_port_ntf=None, m4_fw_name=None, terminator=DFT_TERMINATOR, verbose=False):
        """Constructor.
        :param serial_port: Serial Port device path. Refer to
            `Serial <https://pyserial.readthedocs.io/en/latest/pyserial_api.html#serial.Serial>`_
            for more information.
        :type serial_port: str (eg. /dev/ttyRPMSG0)
        :m4_fw_name: M4 firmare name 
        :type m4_fw_name: str (eg. /usr/local/Cube-M4-examples/STM32MP157C-DK2/Applications/OpenAMP/OpenAMP_TTY_echo/lib/firmware/OpenAMP_TTY_echo.elf)
        """
    
#        self._serial_port_cmd = serial_port
        """Serial Port object."""

        """Last answer received on the serial port when executing a command."""
        try:
            self._verbose = verbose
            self._answers_listener=None
            self._notifications_listener=None
            if serial_port_cmd == serial_port_ntf:
                raise CommsdkInvalidOperationException ("\nError CommAPI serial_port_cmd and serial_port_ntf must be different")
            
            self._terminator = terminator.encode('utf-8')
            self._m4_fw_name = None            
            self._m4_fw_path = None
            if m4_fw_name != None:
                if os.path.isfile(m4_fw_name):
                    self._m4_fw_path, self._m4_fw_name = os.path.split(m4_fw_name)
                    shutil.copyfile(m4_fw_name, "/lib/firmware/"+self._m4_fw_name)

                      # FIXME check if FW is already running: if not rise an exception
                if self._is_M4Fw_running():
                    self._stop_M4Fw()
                    time.sleep(0.5)  # give fw time to stop

                # start m4 Fw
                self._set_M4Fw_name(self._m4_fw_name)
                self._start_M4Fw()
                time.sleep(1)  # give fw time to start                       

            self._serial_port_cmd = serial.Serial()
            self._serial_port_cmd.port = serial_port_cmd
            self._serial_port_cmd.timeout = 1
            if not self._serial_port_cmd.is_open:
                self._serial_port_cmd.open()
            if not self._serial_port_cmd.is_open:            
                if self._verbose:
                    print ("serial port for commands opening failed")

            self._serial_port_ntf = serial_port_ntf
            if serial_port_ntf != None:
                self._serial_port_ntf = serial.Serial()
                self._serial_port_ntf.port = serial_port_ntf
                self._serial_port_ntf.timeout = 1

            self._answer = None
            self._lock_cmd = threading.Lock()

        except (SerialException, SerialTimeoutException, CommsdkInvalidOperationException) as e:
            raise e


    def __del__(self):

        try:

            if self._verbose:
                print ("Deleting CommAPI object")
            if hasattr(self, '_serial_port_cmd') and \
                self._serial_port_cmd != None and \
                self._serial_port_cmd.is_open:
                self._serial_port_cmd.close()
            if hasattr(self, '_serial_port_ntf') and \
                self._serial_port_ntf != None and \
                self._serial_port_ntf.is_open:
                self._serial_port_ntf.close()
            if self._is_M4Fw_running():
                self._stop_M4Fw()
                time.sleep(0.5)  # give fw time to stop

        except (SerialException, SerialTimeoutException, CommsdkInvalidOperationException) as e:
            raise e


    def cmd_get(self, msg=None, timeout=0):
        """Send a request to M4 and wait for the answer (deft)
        :msg: if None just wait for msg from M4. If msg != None send it and wait for M4 answ if any according
              to timeout arg. Msg can be str type or binary type.
              Binary type msg can be used in synchronuos mode only.
        :timeout: if=0 (deft) or -1 blocks until answer from M4 comes (sync mode);
        : if>0 answer is sent back throug CommAPIListener call back on_M4_notify (async mode)
        : return: for blocking call (timeout =0 or -1) str type answer msg, if no answer return ''
                  for non blocking call (timout >0) return 0 if ok, -1 if error
        :type listener: :class:
        """ 
        try:

            if self._lock_cmd.acquire(False):
                if timeout == 0 or timeout ==-1:   # blocking call
                    self._serial_port_cmd.timeout = None
                    if msg==None:  # no cmd_xxx to send, just check for M4 spontaneous msg
                        self._serial_port_cmd.timeout = 1                    
                        self._answer = self._serial_port_cmd.read_until(self._terminator,None)                     
                        self._lock_cmd.release()            
                        return self._answer.decode('utf-8') # if no msg rx return ''
                    if type(msg) == str:
                        if self._verbose:
                           print ("TX:", msg.encode('utf-8'))
                        self._serial_port_cmd.write(msg.encode('utf-8'))
                        self._serial_port_cmd.flush()         
                        self._serial_port_cmd.timeout = 1                        
                        time.sleep(0.5)  # give M4 time to answ
                        self._answer = self._serial_port_cmd.read_until(self._terminator,None)          
                        self._lock_cmd.release() 
                        return self._answer.decode('utf-8')
                    else:  # binary msg type
                        if self._verbose:
                            print ("Tx msg type: ", type(msg))
                            print (msg, len(msg))                        
                        self._serial_port_cmd.timeout = 1                     
                        self._serial_port_cmd.write(msg)                
                        self._serial_port_cmd.flush()         
                        self._answer = self._serial_port_cmd.read(BINARY_ANSW_MAX_LEN) 
                        self._lock_cmd.release()                    
                        return self._answer

                elif timeout > 0 and self._answers_listener != None:  # non blocking call
                    self._serial_port_cmd.timeout = timeout
                    self._th_comm_rx = ThM4Answers(self, "ThM4Answers", self._terminator)
                    self._th_comm_rx.start()                       
                    if self._verbose:
                        print ("TX:", msg.encode('utf-8')+'\n'.encode('utf-8'))
                    self._serial_port_cmd.write(msg.encode('utf-8'))
                    self._serial_port_cmd.flush()         
                elif (timeout): 
                    self._lock_cmd.release()
                    if self._verbose:
                        print ("ERROR call add_notifications_listener before")  # TODO mange API usage error & raise exception
                return 0
            else:   # channel locked by another async outstanding command 
                return -1

        except (SerialException, SerialTimeoutException, CommsdkInvalidOperationException) as e:
            raise e


    def cmd_set(self, msg=None, timeout=0):
        """Send a command to M4. 
        :msg: same as cmd_get
        :type listener: :class:`  `
        """ 
        return self.cmd_get(msg, timeout)


    def add_notifications_listener(self, listener):
        """Add a notifications listener.

        :param listener: Listener to be added.
        :type listener: :class:``
        """
        try:
            if listener is None:
                raise CommsdkInvalidOperationException ("\nError add_notifications_listener: null listener")           
            self._th_ntf = ThM4Notifications(self, "ThM4Notifications", self._terminator, True)            
            self._notifications_listener=listener
            if not self._serial_port_ntf.is_open:
                self._serial_port_ntf.open()                
            if not self._serial_port_ntf.is_open:            
                raise CommsdkInvalidOperationException ("\nError add_notifications_listener: serial port opening failed")
            self._th_ntf.start()
            return 0

        except (SerialException, SerialTimeoutException, CommsdkInvalidOperationException) as e:
            raise e


    def remove_notifications_listener(self, listener):
        """Remove the notifications listener.
        """
        try:

            if listener is None:
                raise CommsdkInvalidOperationException ("\nError remove_notifications_listener: null listener")
            if not self._notifications_listener:
                raise CommsdkInvalidOperationException ("\nError remove_notifications_listener: listener was not added") 
            self._th_ntf.join()    # stop the listening thread
            if self._verbose:
                print ("Notification Thread joined")
            if self._serial_port_ntf.is_open:
                self._serial_port_ntf.close()
            if self._serial_port_ntf.is_open:            
                raise CommsdkInvalidOperationException ("\nError remove_notifications_listener: serial port closing failed")                                
            self._notifications_listener = None
            return 0

        except (SerialException, SerialTimeoutException, CommsdkInvalidOperationException) as e:
            raise e


    def add_answers_listener(self, listener):
        """Add an answers listener.

        :param listener: Listener to be added.
        :type listener: :class:``
        """
        try:

            if listener is None:
                raise CommsdkInvalidOperationException ("\nError add_answers_listener: null listener")
            if not self._lock_cmd.acquire(False):        
                raise CommsdkInvalidOperationException ("\nError add_answers_listener: locked by outstanding command")
            self._answers_listener=listener
            self._lock_cmd.release()        
            return 0

        except (SerialException, SerialTimeoutException, CommsdkInvalidOperationException) as e:
            raise e        


    def remove_answers_listener(self, listener):
        """Remove the answers listener.
        """
        try:

            if listener is None:
                raise CommsdkInvalidOperationException ("\nError remove_answers_listener: null listener")
            if not self._answers_listener:
                raise CommsdkInvalidOperationException ("\nError remove_answers_listener: listener was not added")
            if not self._lock_cmd.acquire(False):        
                raise CommsdkInvalidOperationException ("\nError remove_answers_listener: locked by outstanding command")
            self._answers_listener=None
            self._lock_cmd.release()
            return 0

        except (SerialException, SerialTimeoutException, CommsdkInvalidOperationException) as e:
            raise e        

    def _is_M4Fw_running(self):        
        with open('/sys/class/remoteproc/remoteproc0/state', 'r') as fw_state_fd:
            fw_state = fw_state_fd.read(50).strip()
            fw_state_fd.close()
            if fw_state == "running":
                return True
            return False
            
    def _get_M4Fw_name(self):
        with open('/sys/class/remoteproc/remoteproc0/firmware', 'r') as fw_name_fd:
            name = fw_name_fd.read(100).strip()
            fw_name_fd.close()
            return name
        
    def _set_M4Fw_name(self, name):   #     "how2eldb03110.elf"  
        with open('/sys/class/remoteproc/remoteproc0/firmware', 'r+') as fw_name_fd:
            res = fw_name_fd.write(name)
            fw_name_fd.close()
            return res

    def _start_M4Fw(self):
        with open('/sys/class/remoteproc/remoteproc0/state', 'r+') as fw_state_fd:
            res = fw_state_fd.write("start")
            fw_state_fd.close()
            return res
        
    def _stop_M4Fw(self):
        with open('/sys/class/remoteproc/remoteproc0/state', 'r+') as fw_state_fd:
            res = fw_state_fd.write("stop")
            fw_state_fd.close()
            return res


# INTERFACES

"""listener to the messages from M4 (spontaneous notifications).
It is a thread safe list, so a listener can subscribe itself through a
callback."""


class CommAPINotificationsListener(object):
    """Interface used by the :class:`wire_st_sdk.iolink.IOLinkMaster` class to
    notify changes of a masterboard's status.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def on_M4_notify(self, ntfy_msg):
        """To be called whenever a M4 processor sends a spontaneous notify message.
        :param ntfy_msg: notification msg from M4 utf-8 encoded
        :raises NotImplementedError: is raised if the method is not implemented.
        """
        raise NotImplementedError('You must define "CommAPINotificationsListener()" to use '
            'the "CommAPINotificationsListener" class.')


"""listener to the messages from M4 (answers to cmd_set/cmd_get).
It is a thread safe list, so a listener can subscribe itself through a
callback."""

class CommAPIAnswersListener(object):
    """Interface used by the :class:`wire_st_sdk.iolink.IOLinkMaster` class to
    notify changes of a masterboard's status.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def on_M4_answer(self, answ_msg):
        """To be called whenever a M4 processor sends a spontaneous notify message.
        :param ntfy_msg: notification msg from M4 utf-8 encoded
        :raises NotImplementedError: is raised if the method is not implemented.
        """
        raise NotImplementedError('You must define "on_M4_answer()" to use '
            'the "CommAPIAnswersListener" class.')
    
