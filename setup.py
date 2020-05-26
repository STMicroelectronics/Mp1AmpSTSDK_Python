from setuptools.command.build_py import build_py
from setuptools import setup
import setuptools
import subprocess
import shlex
import sys
import os

VERSION='0.0.4'

def pre_install():
    """Do the custom compiling of the libsdbsdk.so library from the makefile"""
    try:
        print("Working dir is " + os.getcwd())
#        with open("bluepy/version.h","w") as verfile:
#            verfile.write('#define VERSION_STRING "%s"\n' % VERSION)
        for cmd in [ "make -C ./mp1ampstsdk clean", "make -C mp1ampstsdk -j1" ]:
            print("execute " + cmd)
            msgs = subprocess.check_output(shlex.split(cmd), stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print("Failed to compile sdbsdk. Exiting install.")
        print("Command was " + repr(cmd) + " in " + os.getcwd())
        print("Return code was %d" % e.returncode)
        print("Output was:\n%s" % e.output)
        sys.exit(1)

class my_build_py(build_py):
    def run(self):
        pre_install()
        build_py.run(self)

setup_cmdclass = {
    'build_py' : my_build_py,
}

# Force package to be *not* pure Python
# Discusssed at issue #158

try:
    from wheel.bdist_wheel import bdist_wheel

    class sdbsdkBdistWheel(bdist_wheel):
        def finalize_options(self):
            bdist_wheel.finalize_options(self)
            self.root_is_pure = False

    setup_cmdclass['bdist_wheel'] = sdbsdkBdistWheel
except ImportError:
    pass



with open("README.md", "r", encoding='utf-8') as fh:
    long_description = fh.read()

setup(
    name="mp1ampstsdk", 
    version=VERSION,
    author="Licio Mapelli",
    author_email="licio.mapelli@st.com",
    description="MP1 OpenAMP RpMsg A7-M4 communication SDK",
    long_description="OpenAMP RpMsg Py extension to simplify A7-M4 communications",
    long_description_content_type="text/markdown",
    url="https://github.com/mapellil/Mp1AmpSTSDK_Python",
	keywords=[ 'MP1', 'STM', 'STSDK' ],    
    #packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.5",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Development Status :: 3 - Alpha"
    ],
    install_requires=['pyserial>=3'],
    python_requires='>=3.5',
    packages=['mp1ampstsdk'],
    package_data={
        'mp1ampstsdk': ['sdbsdk.c','sdbsdk.h','Makefile','libsdbsdk.so']
    },
    cmdclass=setup_cmdclass,
)
