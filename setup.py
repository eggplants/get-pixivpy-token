from setuptools import find_packages, setup  # type: ignore

setup(
    name='gppt',
    version="1.2",
    description='Get your Pixiv token (for running upbit/pixivpy)',
    description_content_type='',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/eggplants/get-pixiv-token',
    author='eggplants',
    packages=find_packages(),
    python_requires='>=3.5',
    include_package_data=True,
    license='MIT',
    install_requires=open('requirements.txt').read().splitlines(),
    entry_points={
        'console_scripts': [
            'gppt=gppt.main:main'
        ]
    }
)
