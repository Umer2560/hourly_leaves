from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in hourly_leaves/__init__.py
from hourly_leaves import __version__ as version

setup(
	name="hourly_leaves",
	version=version,
	description="Hourly Leaves",
	author="umer",
	author_email="farooqx2560@gmail.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
