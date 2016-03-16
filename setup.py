from setuptools import setup
import os

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.md')).read()
namespace = {}
version_py = open(os.path.join(here, 'rds_cp', 'version.py')).read()
exec(version_py, namespace)

setup(
    name='rds_cp',
    version=namespace['__version__'],
    description="cp for RDS instances",
    long_description=README,
    author='jamesob',
    author_email='jamesob@counsyl.com',
    maintainer='Counsyl Platform Team',
    maintainer_email='opensource@counsyl.com',
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Topic :: Database",
        "Topic :: Software Development",
        "Topic :: System :: Systems Administration",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3 :: Only",
    ],
    py_modules=['rds_cp.rds_cp', 'rds_cp.version'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'boto3==1.1.1',
        'docopt',
    ],
    entry_points={
        'console_scripts': [
            'rds_cp = rds_cp.rds_cp:main',
        ],
    },
)
