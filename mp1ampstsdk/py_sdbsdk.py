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


"""rpmsg_sdb_sdk
The rpmsg_sdb_sdk module is responsible for managing the A7-M4 communication through 
the rpmsg_sdb_driver (Linux kernel) and OpenAMP RpMsg virtual COM port and allocating
the needed memory resources.
"""


# IMPORT

from abc import ABCMeta
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
import time
from datetime import datetime
import threading  
from struct import *
import os
import sys
import ctypes 
from ctypes import *
from ctypes import CFUNCTYPE, POINTER
from mp1ampstsdk.comm_exceptions import CommSDKInvalidOperationException
import subprocess


# CLASSES

class RpmsgSdbAPI():    # TODO make it a singleton object
    """RpmsgSdbAPI class.
    This class manages the communication between the A7 host userland python 
    application and the M4 customized FW through the kernel module rpmsg_sdb_driver
    """

    def __init__(self, m4_fw_name=None, verbose=False):
        """Constructor.
        :param serial_port: Serial Port device path. Refer to
            `Serial <https://pyserial.readthedocs.io/en/latest/pyserial_api.html#serial.Serial>`_
            for more information.
        :type serial_port: str (eg. /dev/ttyRPMSG0)
        :m4_fw_name: M4 firmare path 
        :type m4_fw_name: str (eg. /usr/local/Cube-M4-examples/STM32MP157C-DK2/Applications/OpenAMP/OpenAMP_TTY_echo/lib/firmware/OpenAMP_TTY_echo.elf)
        """
        try:

            self._verbose = verbose
# Insert kernel module stm32_rpmsg_sdb.ko
# TODO ?the kernel module should already be inserted by the distro?
            self._start_sdb_cmd = "insmod /lib/modules/" + str(subprocess.check_output(['uname', '-r']),'utf-8').strip('\n') + "/extra/stm32_rpmsg_sdb.ko"
            os.system(self._start_sdb_cmd)
            time.sleep(0.5)     # give kern drv time to start
            
        # Start M4 Fw if any

            self._m4_fw_name = None            
            self._m4_fw_path = None
            if m4_fw_name != None:
                if os.path.isfile(m4_fw_name):
                    self._m4_fw_path, self._m4_fw_name = os.path.split(m4_fw_name)
                    shutil.copyfile(m4_fw_name, "/lib/firmware/"+self._m4_fw_name)

                if self._is_m4_firmware_running():
                    self._stop_m4_firmware()
                    time.sleep(0.5)  # give fw time to stop

                # start m4 Fw
                self._set_m4_firmware_name(self._m4_fw_name)
                self._start_m4_firmware()
                time.sleep(1)  # give fw time to start
            # if m4_fw_name == None: assumes m4 FW was already started by someone else

            self._buff_num = 0
            self._buff_size = 0      

            temp = os.path.abspath(__file__)
            temp = os.path.realpath(temp)
            temp = os.path.dirname(temp)
            libname = os.path.join(temp, "libsdbsdk.so")
            self._sdb_drv = CDLL(libname)
            if self._sdb_drv == None:
                if self._is_m4_firmware_running():
                    self._stop_m4_firmware()      
                raise CommSDKInvalidOperationException("\nError: library 'libsdbsdk.so' not found. Please build it again.")
        #        CB_FTYPE_CHAR_P = CFUNCTYPE(c_int, c_char_p, c_uint) 
            CB_FTYPE_CHAR_P = CFUNCTYPE(c_int, POINTER(c_char), c_uint) 
            self._cb_get_buffer = CB_FTYPE_CHAR_P(self._buffer_ready_cb) 
            self._sdb_buffer_rx_listener = None

        except (CommSDKInvalidOperationException) as e:
            raise e        
        return              

    def __del__(self):
        if self._verbose:
            print("Deleting RpmsgSdbAPI object")
        if (self._m4_fw_name != None and self._get_m4_firmware_name() == self._m4_fw_name):
            if self._verbose:
                print("RpmsgSdbAPI obj stopping M4 FW: ", self._m4_fw_name)
            self._stop_m4_firmware()
        while (self._is_m4_firmware_running()):
             time.sleep(0.3)  # give M4 FW time to stop
        self._sdb_buffer_rx_listener = None             
        if self._verbose:
            print("RpmsgSdbAPI removing stm32_rpmsg_sdb.ko kernel mod")
        os.system("rmmod stm32_rpmsg_sdb.ko")


    def init_sdb(self, buffsize, buffnum): 
        try:

            if (self._sdb_drv.InitSdbReceiver() !=0):
                raise CommSDKInvalidOperationException("\nError init_sdb failed")              
            self._buff_num = buffnum
            self._buff_size = buffsize        
            self._sdb_drv.register_buff_ready_cb(self._cb_get_buffer)                          
            if (self._sdb_drv.InitSdb(self._buff_size, self._buff_num) != 0):
                raise CommSDKInvalidOperationException("\nError init_sdb failed")

        except (CommSDKInvalidOperationException) as e:
            raise e        

    def deinit_sdb(self):
        self._sdb_drv.DeInitSdbReceiver()
        return self._sdb_drv.unregister_buff_ready_cb(self._cb_get_buffer)


    def start_sdb_receiver(self):
        return self._sdb_drv.StartSdbReceiver()


    def stop_sdb_receiver(self):
        return self._sdb_drv.StopSdbReceiver()


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

        
    def _set_m4_firmware_name(self, name):   #     "how2eldb03110.elf"  
        with open('/sys/class/remoteproc/remoteproc0/firmware', 'r+') as fw_name_fd:
            res = fw_name_fd.write(name)
            fw_name_fd.close()
            return res


    def _start_m4_firmware(self):
        with open('/sys/class/remoteproc/remoteproc0/state', 'r+') as fw_state_fd:
            res = fw_state_fd.write("start")
            fw_state_fd.close()
            return res

        
    def _stop_m4_firmware(self):
        with open('/sys/class/remoteproc/remoteproc0/state', 'r+') as fw_state_fd:
            res = fw_state_fd.write("stop")
            fw_state_fd.close()
            return res

        
    def add_sdb_buffer_rx_listener(self, listener):
        """Add a listener.
        :param listener: Listener to be added.
        :type listener: :class:``
        """
        try:

            if listener is None:
                raise CommSDKInvalidOperationException("\nError add_sdb_buffer_rx_listener: null listener")

    #        self._th_ntf = ThM4Notifications(self, "ThM4Notifications")            
            self._sdb_buffer_rx_listener=listener
            return 0

        except (CommSDKInvalidOperationException) as e:
            raise e

    def remove_sdb_buffer_rx_listener(self, listener):
        """Remove a listener.
        :param listener: Listener to be removed.
        :type listener: :class:``
        """
        try:

            if not self._sdb_buffer_rx_listener:
                raise CommSDKInvalidOperationException("\nError remove_sdb_notification_listener: listener was not added")
            self._sdb_buffer_rx_listener = None
            return 0        

        except (CommSDKInvalidOperationException) as e:
            raise e


    def _buffer_ready_cb(self, sdb_buff, sdb_buff_len):
        if self._verbose:
            print("CB _buffer_ready_cb called buff len: ", sdb_buff_len)
        if self._sdb_buffer_rx_listener is not None:
            self._sdb_buffer_rx_listener.on_m4_sdb_rx(sdb_buff, sdb_buff_len)
        return 0

# INTERFACES

class RpmsgSdbAPIListener(object):
    """Interface used by the :class:` ` to
    notify Shared Data Buffer received form M4.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def on_m4_sdb_rx(self, sdb, sdb_len):
        """To be called whenever a M4 processor sends a sdb buffer.
        :param sdb: sdb buffer from M4 
        :param sdb_len: sdb buffer length from M4         
        :raises NotImplementedError: is raised if the method is not implemented.
        """
        raise NotImplementedError("You must define \"on_m4_sdb_rx()\" to use "
            "the \"RpmsgSdbAPIListener\" class.")


