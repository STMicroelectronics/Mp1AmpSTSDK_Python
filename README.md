# CommSTSDK_Python

CommSTSDK_Python is a Python3 SDK from STMicroelectronics simplifing the virtual serial OpenAMP RpMsgs communiction between the A7 and M4 processors in the MP1 SoC. The SDK is meant to help and speed-up Python developpers not familiar with C OpenAMP development. 
The SDK is divided in two modules:
-- commsdk.py: simple serial protocol based on the set/get/notify paradigm 
-- sdbsdk.py: Shared Data Buffer sdk simplifying the large bynary data buffers exchange between A7 and M4

## Dependencies
The CommSTSDK_Python depends on the following:
 - 
 - 

## Installation
The CommSTSDK_Python can be download to a PC from its GitHub repository.
First, move to the <layers> directory of your distribution, e.g.:
  ```Shell
  $ pip3 install commsdk
  ```
Clone the GitHub repository:
  ```Shell
  $ git clone https://github.com/STMicroelectronics/meta-commsdk.git
  ```
Enter the configuration folder, e.g.:
  ```Shell
  $ cd <path-to>/openstlinux-<version>/build-openstlinuxweston-stm32mp1/conf/
  ```
Copy and paste the following line within the “bblayers.conf” file, just before the “BBLAYERS” token definition, and check that the “BBLAYERS” token contains the “FRAMEWORKLAYERS” token, otherwise add it:
  ```Shell
FRAMEWORKLAYERS += "${@'${OEROOT}/layers/meta-commsdk' if os.path.isfile('${OEROOT}/layers/meta-commsdk/conf/layer.conf') else ''}" else ''}"
BBLAYERS =+ "${OEROOT}/layers/meta-openembedded/meta-python"
BBLAYERS =+ "${OEROOT}/layers/meta-virtualization"
  ```
You can now build your distribution with BitBake.


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
