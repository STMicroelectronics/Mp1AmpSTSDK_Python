import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="commsdk", # Replace with your own username
    version="0.0.1",
    author="Licio Mapelli",
    author_email="licio.mapelli@st.com",
    description="MP1 OpenAMP RpMsg communication SDK",
    long_description="OpenAMP RpMsg Py extension to simplify A7-M4 communications",
    long_description_content_type="text/markdown",
    url="https://github.com/mapellil/CommSTSDK_Python",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.5',
)