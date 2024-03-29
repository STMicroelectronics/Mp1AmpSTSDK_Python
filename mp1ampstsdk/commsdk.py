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
from mp1ampstsdk.comm_exceptions import CommSDKInvalidOperationException
import serial
import threading  
import os
import sys
import time
import shutil


# CONSTANTS

DFT_TERMINATOR = ';'
"""Serial msgs terminator character."""
BINARY_ANSW_MAX_LENGHT = 512
"""Maximum allowed binary message lenght."""


# CLASSES

class M4ResponseThread(threading.Thread):

    def __init__(self, caller, terminator, verbose=False):
        super().__init__()   
        self._caller = caller
        self._terminator = terminator
        self._verbose = verbose


    def run(self):
        try:
            if self._verbose:
                print("CommAPI: Starting M4ResponseThread.")
            self._response = self._caller._serial_port_cmd.read_until(self._terminator,None)
            self._caller._lock_cmd.release()
            if self._verbose:
                print("CommAPI: Lock released.")
                print("CommAPI: Rx Response: \"%s\"" % (self._response.decode("utf-8")))
            if self._caller._response_listener:
                if self._response.decode("utf-8") == "":  # TODO command timeout: generate ad-hoc msg 
                    self._response = "Timeout".encode("utf-8")
                self._caller._response_listener.on_m4_response(self._response.decode("utf-8"))                    
            else:
                raise CommSDKInvalidOperationException("CommAPI: Error response listener to be added.")                

        except (Exception, SerialException, SerialTimeoutException, CommSDKInvalidOperationException) as e:
            if self._caller._serial_port_cmd.is_open:
                self._caller._serial_port_cmd.close()
            self._caller._response_listener = None            
            raise e


    def __del__(self):
        if self._verbose:
            print("CommAPI: Deleting M4ResponseThread.")


class M4NotificationThread(threading.Thread):

    def __init__(self, caller, terminator, verbose=False):
        super().__init__()   
        self._caller = caller
        self._evt_stop_notification = threading.Event()
        self._evt_stop_notification.clear()
        self._terminator = terminator
        self._verbose = verbose


    def run(self):

        try:
            # Enabling spontaneous notifications by writing the OpenAMP RPMSG port at least once with a non-null 
            # character: the A7 has to send the first message to initialize the connection.
            # 
            # For the RPMSG protocol both sides have to know the remote destination address to send a message.
            # On M4 boot, the M4 sends a name service announcement RPMSG on Virtual UART init (linked to the endpoint creation),
            # the M4 provides to the A7 its endpoint address (0x0) by sending the message to a specific address (0x35).
            # If the M4 started to send a new message, then OpenAMP would not know the destination address, thus failing;
            # hence, it's the A7 that has to send a first message, so that it provides his address(0x400) as source of the message
            # itself to the M4 address (0x0). Then, the OpenAMP associates the address and knows the A7 destination address.
            #
            # https://wiki.st.com/stm32mpu/wiki/Coprocessor_management_troubleshooting_grid
            if self._verbose:
                print("CommAPI: Starting M4NotificationThread.")
            self._caller._serial_port_notification.write(self._terminator)
            #ret = self._caller._serial_port_notification.read_until(self._terminator, None)   # wait for spurious echo if any                
            self._caller._serial_port_notification.flush() 

            while True:
                if self._evt_stop_notification.isSet():
                    self._evt_stop_notification.clear() 
                    if self._verbose:
                        print("CommAPI: Stopping M4NotificationThread.")
                    return
                self._notification = self._caller._serial_port_notification.read_until(self._terminator, None)
                if self._verbose and self._notification != "":
                    print("CommAPI: Rx Notification: \"%s\""% (self._notification.decode("utf-8")))
                if self._notification.decode("utf-8") != "":
                    if self._caller._notification_listener:
                        self._caller._notification_listener.on_m4_notification(self._notification.decode("utf-8"))
                    else:
                        raise CommSDKInvalidOperationException("CommAPI: Error notification listener to be added.")

        except (Exception, SerialException, SerialTimeoutException, CommSDKInvalidOperationException) as e:
            if self._caller._serial_port_notification.is_open:
                self._caller._serial_port_notification.close()
            self._caller._notification_listener = None            
            raise e


    def join(self, timeout=None):

        if self._verbose:
            print("CommAPI: Joining M4NotificationThread.")
        self._evt_stop_notification.set()
        super().join(timeout) 


    def __del__(self):
        if self._verbose:
            print("CommAPI: Deleting M4NotificationThread.")


class CommAPI():
    """CommAPI class.
    This class manages the communication via OpenAMP serial Rpmsg between the A7
    and the M4.
    """

    _SERIAL_PORT_RESPONSE_TIMEOUT_s = 1
    """Timeout for responses."""

    _SERIAL_PORT_NOTIFICATION_TIMEOUT_s = 1
    """Timeout for notifications."""

    def __init__(self, serial_port_cmd, serial_port_notification=None, m4_fw_name=None, terminator=DFT_TERMINATOR, verbose=False):
        """Constructor.
        :param serial_port_cmd: Absolute path of the Serial Port device used for commands and responses.
            E.g.: '/dev/ttyRPMSG0'.
            Refer to
            `Serial <https://pyserial.readthedocs.io/en/latest/pyserial_api.html#serial.Serial>`_
            for more information.
        :type serial_port_cmd: str

        :param serial_port_notification: Absolute path of the Serial Port device used for notifications.
            E.g.: '/dev/ttyRPMSG1'.
            Refer to
            `Serial <https://pyserial.readthedocs.io/en/latest/pyserial_api.html#serial.Serial>`_
            for more information.
        :type serial_port_notification: str

        :param m4_fw_name: Absolute path of the M4 firmware.
            E.g.: '/usr/local/Cube-M4-examples/STM32MP157C-DK2/Applications/OpenAMP/OpenAMP_TTY_echo/lib/firmware/OpenAMP_TTY_echo.elf'.
        :type m4_fw_name: str

        :param terminator: Terminator sequence used to separate messages on the serial ports.
            E.g.: ';'.
        :type terminator: str

        :param verbose: If True, enables verbosity on output.
        :type verbose: boolean
        """
        try:
            self._verbose = verbose
            self._response_listener = None
            self._notification_listener = None
            self._released = False

            if self._verbose:
                print("CommAPI: Creating CommAPI object.")

            if serial_port_cmd == serial_port_notification:
                raise CommSDKInvalidOperationException("CommAPI: Error CommAPI: \"serial_port_cmd\" and \"serial_port_notification\" must be different.")

            self._terminator = terminator.encode("utf-8")
            self._m4_fw_name = None            
            self._m4_fw_path = None
            if m4_fw_name != None:
                if os.path.isfile(m4_fw_name):
                    self._m4_fw_path, self._m4_fw_name = os.path.split(m4_fw_name)
                    shutil.copyfile(m4_fw_name, "/lib/firmware/" + self._m4_fw_name)

                # FIXME check if FW is already running: if not rise an exception
                if self._is_m4_firmware_running():
                    self._stop_m4_firmware()
                    # Checking for virtual com ports closed.
                    if os.path.exists(serial_port_cmd) or \
                        os.path.exists(serial_port_notification):
                        raise CommSDKInvalidOperationException(
                            "CommAPI: OpenAMP error. Please reboot your device.")

                # start m4 Fw
                self._set_m4_firmware_name(self._m4_fw_name)
                self._start_m4_firmware()
                # Checking for virtual com ports open.
                while not os.path.exists(serial_port_cmd):
                    pass
                if serial_port_notification:
                    while not os.path.exists(serial_port_notification):
                        pass

            self._serial_port_cmd = serial.Serial()
            self._serial_port_cmd.port = serial_port_cmd
            self._serial_port_cmd.timeout = self._SERIAL_PORT_RESPONSE_TIMEOUT_s
            if not self._serial_port_cmd.is_open:
                self._serial_port_cmd.open()
            if not self._serial_port_cmd.is_open:            
                if self._verbose:
                    raise CommSDKInvalidOperationException("CommAPI: Error: opening serial port for commands failed.")

            if serial_port_notification != None:
                self._serial_port_notification = serial.Serial()
                self._serial_port_notification.port = serial_port_notification
                self._serial_port_notification.timeout = self._SERIAL_PORT_NOTIFICATION_TIMEOUT_s
                if not self._serial_port_notification.is_open:
                    self._serial_port_notification.open()
                if not self._serial_port_notification.is_open:            
                    raise CommSDKInvalidOperationException("CommAPI: Error: opening serial port for notifications failed.")

            self._response = None
            self._lock_cmd = threading.Lock()

        except (Exception, SerialException, SerialTimeoutException, CommSDKInvalidOperationException) as e:
            raise e


    def __del__(self):
        """Deleting object.
        """
        if self._verbose:
            print("CommAPI: Deleting CommAPI object.")
        if not self._released:
            self.release()


    def release(self):
        """Release resources.
        """
        try:
            if self._verbose:
                print("CommAPI: Releasing resources.")
            if hasattr(self, '_serial_port_cmd') and \
                self._serial_port_cmd and \
                self._serial_port_cmd.is_open:
                self._serial_port_cmd.close()
                del self._serial_port_cmd
            if hasattr(self, '_serial_port_notification') and \
                self._serial_port_notification and \
                self._serial_port_notification.is_open:
                self._serial_port_notification.close()
                del self._serial_port_notification
            if self._is_m4_firmware_running():
                self._stop_m4_firmware()
            self._released = True
            del self

        except (Exception, SerialException, SerialTimeoutException, CommSDKInvalidOperationException) as e:
            raise e


    def cmd_get(self, msg=None, timeout=0):
        """Send a request to M4 and wait for the response (deft)
        :msg: if None just wait for msg from M4. If msg != None send it and wait for M4 response if any according
              to timeout arg. Msg can be str type or binary type.
              Binary type msg can be used in synchronuos mode only.
        :timeout: if=0 (deft) or -1 blocks until response from M4 comes (sync mode);
        : if>0 response is sent back throug CommAPIListener call back on_m4_notification (async mode)
        : return: for blocking call (timeout =0 or -1) str type response msg, if no response return ''
                  for non blocking call (timout >0) return 0 if ok, -1 if error
        :type listener: :class:
        """
        try:

            if self._lock_cmd.acquire(False):
                if self._verbose:
                    print("CommAPI: Lock acquired.")
                if timeout == 0 or timeout ==-1:   # blocking call
                    self._serial_port_cmd.timeout = None
                    if msg==None:  # no cmd_xxx to send, just check for M4 spontaneous msg
                        self._serial_port_cmd.timeout = 1                    
                        self._response = self._serial_port_cmd.read_until(self._terminator,None)
                        self._lock_cmd.release()
                        if self._verbose:
                            print("CommAPI: Lock released.")
                        return self._response.decode("utf-8") # if no msg rx return ''
                    if type(msg) == str:
                        #print("CommAPI: Tx:", msg.encode("utf-8"))
                        self._serial_port_cmd.write(msg.encode("utf-8"))
                        self._serial_port_cmd.flush()
                        self._serial_port_cmd.timeout = 1
                        time.sleep(0.5)  # give M4 time to respond
                        self._response = self._serial_port_cmd.read_until(self._terminator,None)
                        self._lock_cmd.release()
                        if self._verbose:
                            print("CommAPI: Lock released.")
                        return self._response.decode("utf-8")
                    else:  # binary msg type
                        #print("CommAPI: Tx msg type: ", type(msg))
                        #print(msg, len(msg))
                        self._serial_port_cmd.timeout = 1
                        self._serial_port_cmd.write(msg)
                        self._serial_port_cmd.flush()
                        self._response = self._serial_port_cmd.read(BINARY_ANSW_MAX_LENGHT) 
                        self._lock_cmd.release()
                        if self._verbose:
                            print("CommAPI: Lock released.")
                        return self._response

                elif timeout > 0 and self._response_listener != None:  # non blocking call
                    self._th_comm_rx = M4ResponseThread(self, self._terminator, self._verbose)
                    self._th_comm_rx.start()                       
                    #print("CommAPI: Tx:", msg.encode("utf-8")+'\n'.encode("utf-8"))
                    self._serial_port_cmd.timeout = timeout
                    self._serial_port_cmd.write(msg.encode("utf-8"))
                    self._serial_port_cmd.flush()
                elif (timeout): 
                    self._lock_cmd.release()
                    if self._verbose:
                        print("CommAPI: Lock released.")
                        print("CommAPI: ERROR call add_notification_listener before.")  # TODO mange API usage error & raise exception
                return 0
            else:   # channel locked by another async outstanding command 
                return -1

        except (Exception, SerialException, SerialTimeoutException, CommSDKInvalidOperationException) as e:
            raise e


    def cmd_set(self, msg=None, timeout=0):
        """Send a command to M4. 
        :msg: same as cmd_get
        :type listener: :class:`  `
        """ 
        return self.cmd_get(msg, timeout)


    def add_notification_listener(self, listener):
        """Add a notification listener.

        :param listener: Listener to be added.
        :type listener: :class:``
        """
        try:
            if listener is None:
                raise CommSDKInvalidOperationException("CommAPI: Error add_notification_listener(): provide a valid listener.")
            self._notification_listener = listener
            if not self._serial_port_notification.is_open:
                self._serial_port_notification.open()                
            if not self._serial_port_notification.is_open:            
                raise CommSDKInvalidOperationException("CommAPI: Error add_notification_listener(): serial port opening failed.")
            self._th_notification = M4NotificationThread(self, self._terminator, self._verbose)
            self._th_notification.start()
            return 0

        except (Exception, SerialException, SerialTimeoutException, CommSDKInvalidOperationException) as e:
            raise e


    def remove_notification_listener(self, listener):
        """Remove a notification listener.
        """
        try:

            if listener is None:
                raise CommSDKInvalidOperationException("CommAPI: Error remove_notification_listener(): provide a valid listener.")
            if not self._notification_listener:
                raise CommSDKInvalidOperationException("CommAPI: Error remove_notification_listener(): the listener was not added.") 
            self._th_notification.join()    # stop the listening thread
            if self._serial_port_notification.is_open:
                self._serial_port_notification.close()
            if self._serial_port_notification.is_open:            
                raise CommSDKInvalidOperationException("CommAPI: Error remove_notification_listener(): serial port closing failed.")                                
            self._th_notification = None    # delete the listening thread
            self._notification_listener = None
            return 0

        except (Exception, SerialException, SerialTimeoutException, CommSDKInvalidOperationException) as e:
            raise e


    def add_response_listener(self, listener):
        """Add a response listener.

        :param listener: Listener to be added.
        :type listener: :class:``
        """
        try:

            if listener is None:
                raise CommSDKInvalidOperationException("CommAPI: Error add_response_listener(): provide a valid listener.")
            if not self._lock_cmd.acquire(False):        
                raise CommSDKInvalidOperationException("CommAPI: Error add_response_listener(): locked by outstanding command.")
            if self._verbose:
                print("CommAPI: Lock acquired.")
            self._response_listener = listener
            self._lock_cmd.release()
            if self._verbose:
                print("CommAPI: Lock released.")
            return 0

        except (Exception, SerialException, SerialTimeoutException, CommSDKInvalidOperationException) as e:
            raise e        


    def remove_response_listener(self, listener):
        """Remove a responses listener.
        """
        try:
            if listener is None:
                raise CommSDKInvalidOperationException("CommAPI: Error remove_response_listener(): provide a valid listener.")
            if not self._response_listener:
                raise CommSDKInvalidOperationException("CommAPI: Error remove_response_listener(): the listener was not added.")
            if not self._lock_cmd.acquire(False):
                raise CommSDKInvalidOperationException("CommAPI: Error remove_response_listener(): locked by outstanding command.")
            if self._verbose:
                print("CommAPI: Lock acquired.")
            self._response_listener = None
            self._lock_cmd.release()
            if self._verbose:
                print("CommAPI: Lock released.")
            return 0

        except (Exception, SerialException, SerialTimeoutException, CommSDKInvalidOperationException) as e:
            raise e        


    def _is_m4_firmware_running(self):        
        with open('/sys/class/remoteproc/remoteproc0/state', 'r') as fw_state_fd:
            fw_state = fw_state_fd.read(50).strip()
            fw_state_fd.close()
            if fw_state == "running":
                return True
            return False


    def _get_m4_firmware_name(self):
        with open('/sys/class/remoteproc/remoteproc0/firmware', 'r') as fw_name_fd:
            name = fw_name_fd.read(100).strip()
            fw_name_fd.close()
            return name


    def _set_m4_firmware_name(self, name):
        with open('/sys/class/remoteproc/remoteproc0/firmware', 'r+') as fw_name_fd:
            res = fw_name_fd.write(name)
            fw_name_fd.close()
            return res


    def _start_m4_firmware(self):
        if self._verbose:
            print("CommAPI: Starting firmware on M4.")
        with open('/sys/class/remoteproc/remoteproc0/state', 'r+') as fw_state_fd:
            res = fw_state_fd.write("start")
            fw_state_fd.close()
            #time.sleep(0.5)  # give fw time to start.
            return res


    def _stop_m4_firmware(self):
        if self._verbose:
            print("CommAPI: Stopping firmware on M4.")
        with open('/sys/class/remoteproc/remoteproc0/state', 'r+') as fw_state_fd:
            res = fw_state_fd.write("stop")
            fw_state_fd.close()  # give fw time to stop.
            #time.sleep(0.5)
            return res


# INTERFACES

"""listener to the messages from M4 (spontaneous notifications).
It is a thread safe list, so a listener can subscribe itself through a
callback."""

class CommAPINotificationListener(object):
    """Interface used by the :class:`wire_st_sdk.iolink.IOLinkMaster` class to
    notify changes of a masterboard's status.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def on_m4_notification(self, notificationy_msg):
        """To be called whenever a M4 processor sends a spontaneous notify message.
        :param notificationy_msg: notification msg from M4 utf-8 encoded
        :raises NotImplementedError: is raised if the method is not implemented.
        """
        raise NotImplementedError("You must define \"on_m4_notification()\" to "
            "use the \"CommAPINotificationListener\" class.")


"""listener to the messages from M4 (responses to cmd_set/cmd_get).
It is a thread safe list, so a listener can subscribe itself through a
callback."""

class CommAPIResponseListener(object):
    """Interface used by the :class:`wire_st_sdk.iolink.IOLinkMaster` class to
    notify changes of a masterboard's status.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def on_m4_response(self, response):
        """To be called whenever a M4 processor sends a spontaneous notify message.
        :param notificationy_msg: notification msg from M4 utf-8 encoded
        :raises NotImplementedError: is raised if the method is not implemented.
        """
        raise NotImplementedError("You must define \"on_m4_response()\" to use "
            "the \"CommAPIResponseListener\" class.")
