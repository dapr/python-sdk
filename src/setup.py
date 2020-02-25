import setuptools
with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="dapr-client",
    version="0.2.0.b1",
    author="dapr.io",
    author_email="pypidapr@microsoft.com",
    description="Dapr client sdk using gRPC.",
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
