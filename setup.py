import setuptools
with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="dapr-sdk",
    version="0.3.0.b1",
    author="dapr.io",
    author_email="daprweb@microsoft.com",
    description="Dapr SDK",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://dapr.io/",
    packages=setuptools.find_packages(),
    install_requires=[
          'protobuf',
          'grpcio'
      ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
