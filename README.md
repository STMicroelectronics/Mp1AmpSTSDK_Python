# CommSTSDK_Python

CommSTSDK_Python is a Python3 SDK from STMicroelectronics simplifing the virtual serial OpenAMP RpMsgs communiction between the A7 and M4 processors in the MP1 SoC. The SDK is meant to help and speed-up Python developpers not familiar with C OpenAMP development and Linux kernel drivers interface.
The SDK is divided in two modules:
-- commsdk.py: simple serial protocol based on the set/get/notify paradigm, transporting ASCCI UTF-8 strings. 
-- py_sdbsdk.py: Shared Data Buffer sdk simplifying the large bynary data buffers exchange between A7 and M4 through OpenAMP and dedicated Linux external kernel driver
-- sdbsdk.c: is the C backend of py_sdbsdk.py representing the user side API of stm32_rpmsg_sdb.ko kernel object 

This python package is meant to be run on the MP1-DK2 board only, this is because of the subtending HW dependecies (eg. kernel drv object, OpenAMP RpMsg, Shared Memory and associated M4 slave processor FW to communicate with)

## Python dependencies
The CommSTSDK_Python depends on the following:
 - pyserial
 The above dependencies are automatically resolved during pip3 install phase or within the dedicate Yocto layer

## Compile dependencies



## Installation
The CommSTSDK_Python can be download from its Pypi repository.

  ```Shell
  $ pip install -i https://test.pypi.org/simple/ commsdk
  ```

## Package creation from src
To regenerate the package the best is to setup a MP1-DK2 Rev.C board flashing it with the OpenSTLinux distro V1.2 adding the dedicated Python layer (including pip and the build essentials). From the DK2 shell install the following pkgs:

  ```Shell
  $ pip3 install wheel
  $ pip3 install twine
  ```
  
Then, from the MP1-DK2 shell Clone the github repo entering:

  ```Shell
  $ git clone https://github.com/mapellil/CommSTSDK_Python.git
  ```

Make the desired modifications to src files and then in the setup.py increase the VERSION number, than
create the Pypi package:
  ```Shell
  $ python3 setup.py sdist bdist_wheel

  ```
and upload it on pypi repo:
  ```Shell
  $ python3 -m twine upload --skip-existing --repository-url https://test.pypi.org/legacy/  dist/*
  ```

For you convenience a shell script is provided, see file build_pypi_pkg.sh, creating the pypi pkg and uploading it on the pypi repo.

To modify the associated Linux external kernel driver "stm32-rpmsg-sdb.ko" it needs to recompile and flash the whole distibution as the source of this driver is contained into the associated layer. To avoid flashing the board a possible shortcut is to directly copy the compiled .ko form the host into the DK2 target through scp command.

## M4 FW modifications from src
To run the pkg and its associated demo two M4 Fw are needed on DK-2 target:
-- OpenAMP_TTY_echo.elf to run the demo_commsdk.py "commsdk" test
-- how2eldb04120.elf to run the demo_commsdk.py "sdbsdk" test
The M4 Fw needs to be cross compiled from the IDE SystemWorkbench-2.4.0 (/mnt/storage/MP1/STM32-CoPro-MPU_Full_Install_linux64_0.4.8/SystemWorkbench-2.4.0_mpu) or STM32CubeIDE or EWARM or MDK-ARM so first install your preferred  IDE. 
The M4 FW how2eldb04120.elf is available at https://github.com/STMicroelectronics/logicanalyser
The M4 FW OpenAMP_TTY_echo.elf is available within the STM32CubeMP1 MPU Firmware Package at https://github.com/STMicroelectronics/STM32CubeMP1
Both the M4 FW packages needs to be installed at the same directory level to allow resolving cross dependencies within the how2eldb04120 project. 


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
