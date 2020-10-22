# Mp1AmpSTSDK_Python

Mp1AmpSTSDK_Python is a Python3 SDK from STMicroelectronics simplifing the virtual serial OpenAMP RpMsgs communiction between the A7 and M4 processors in the MP1 SoC. The SDK is meant to help and speed-up Python developpers not familiar with C OpenAMP development and Linux kernel drivers interface.
The SDK is divided in two modules:
- commsdk.py: simple serial protocol based on the set/get/notify paradigm, transporting ASCCI UTF-8 strings. 
- py_sdbsdk.py: Shared Data Buffer sdk simplifying the large bynary data buffers exchange between A7 and M4 through OpenAMP and dedicated Linux external kernel driver
- sdbsdk.c: is the C backend of py_sdbsdk.py representing the user side API of stm32_rpmsg_sdb.ko external kernel object. The compilation of sdbsdk.c file generates the libsdbsdk.so which is the User space wrapper library containing API of the above described kernel module. 

This python package is meant to be run on the MP1-DK2 board, this is because of the subtending HW dependecies (eg. kernel drv object, OpenAMP RpMsg, Shared Memory and associated M4 slave processor FW to communicate with)
In case is needed only the OpenAMP virtual comm port functionality the pkg can be considered as "pure python3" with no dependendecies (except OpenAMP). While, if the sdbsdk (Shared Data Buffer) functionality is needed, the pkg has dependencies to the internally generated shared object (python3/C mixed code) and to the layer https://github.com/STMicroelectronics/meta-st-py3-ext generating the stm32_rpmsg_sdb.ko kernel object which must be included in the distribution.

## Python dependencies
The Mp1AmpSTSDK_Python depends on the following:
 - pyserial
 The above dependencies are automatically resolved during pip3 install phase or within the dedicate Yocto layer

## Installation
The CommSTSDK_Python can be installed from its Pypi repository.

  ```Shell
  $ pip3 install mp1ampstsdk
  ```

## Package creation/modifications from src
To regenerate the package the best is to setup a MP1-DK2 Rev.C board flashing it with the OpenSTLinux distro V1.2 including the dedicated Python layer (including pip and the build essentials). The support Yocto layer can be found at:
```
https://github.com/STMicroelectronics/meta-st-py3-ext
```
The step above, so having the whole Yocto ST "Distribution package" plus the above layer, is mandatory only in case the required modifications involve the associated kernel driver; otherwise in case the modifications are limited to the python part or to the C part the step above can be skipped and the modifications can be done directly on the DK-2 board following the steps below.

From the DK2 shell install the following pkgs:

  ```Shell
  $ pip3 install wheel
  $ pip3 install twine
  ```
  
Then, from the MP1-DK2 shell Clone the github repo entering:

  ```Shell
  $ git clone https://github.com/STMicroelectronics/Mp1AmpSTSDK_Python.git
  ```

Make the desired modifications to src files and then in the setup.py increase the VERSION number, than
create the Pypi package:
  ```Shell
  $ python3 setup.py sdist bdist_wheel

  ```
and upload it on pypi repo:
  ```Shell
  $ python3 -m twine upload --skip-existing --repository pypi dist/*
  ```
in case a pypi test is needed upload the new pkg on test.pypi repo:
  ```Shell
  $ python3 -m twine upload --skip-existing --repository-url https://test.pypi.org/legacy/  dist/*
  ```


For you convenience a shell script is provided, see file build_pypi_pkg.sh, creating the pypi pkg and uploading it on the pypi repo.

### External Kernel Driver modifications
To modify the associated Linux external kernel driver "stm32-rpmsg-sdb.ko" it needs to recompile and flash the whole distibution as the source of this driver is contained into the associated above indicated layer. To avoid flashing the board a possible shortcut is to directly copy the compiled .ko form the host into the DK2 target through scp command. Notice that, if the modifications done at kernel driver level are impacting also the C wrapper (generating .so module) it needs to recompile it on the DK-2 board running the setup script with the command "python3 setup.py sdist bdist_wheel".
For convenience, while developping on the DK-2 board, after having cloned the whole py pkg and applied modfications, it can be addressed setting the environemntal variable"
```
 $ export PYTHONPATH=<py pkg cloned folder>
```

### M4 FW modifications from src
To run the pkg and its associated demo two M4 Fw (precompiled .elf) have to be installed on DK-2 target:
- OpenAMP_TTY_echo.elf to run the demo_commsdk.py "commsdk" test
- how2eldb04120.elf to run the demo_commsdk.py "sdbsdk" test
To generate the two .elf the M4 Fw needs to be cross compiled from the IDE SystemWorkbench-2.4.0 (/mnt/storage/MP1/STM32-CoPro-MPU_Full_Install_linux64_0.4.8/SystemWorkbench-2.4.0_mpu) or STM32CubeIDE or EWARM or MDK-ARM so first install your preferred  IDE on the host.
The project for the M4 FW "how2eldb04120" is available at https://github.com/STMicroelectronics/logicanalyser
The project for the M4 FW "OpenAMP_TTY_echo" is available within the "STM32CubeMP1 MPU Firmware Package" at https://github.com/STMicroelectronics/STM32CubeMP1
Both the M4 FW packages needs to be installed at the same root directory level to allow resolving cross dependencies within the how2eldb04120 project. 
Once the new .elf is obtained, for a quick test is possible to scp it on the DK-2 target; otherwise to deliver in the distro the new M4FW together with its dedicated Yocto layer just copy the .elf in the "firmware" folder of the layer. 


## Open Points
 
 - Demo:
  The sdbsdk demo could be extended in order to use asynchronous cmds/answers to M4
  The demo could trap exceptions from below layers
   
 - py_sdbsdk.py:
  The RpmsgSdbAPI should be transformed in singleton obj

- sdbsdk.c:
  In some system calls, within the C thread, in the case of fails (eg ioctl, poll) the roll back is not handled as it should imply the thread exit and raising somehow asynchrouns exception up to python level. 



## License
COPYRIGHT(c) 2020 STMicroelectronics

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
  1. Redistributions of source code must retain the above copyright notice,
     this list of conditions and the following disclaimer.
  2. Redistributions in binary form must reproduce the above 
     notice, this list of conditions and the following disclaimer in the
     documentation and/or other materials provided with the distribution.
  3. Neither the name of STMicroelectronics nor the names of its
     contributors may be used to endorse or promote products derived from
     this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
