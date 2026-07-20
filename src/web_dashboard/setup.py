from setuptools import find_packages, setup
setup(
    name='web_dashboard',
    version='2.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index', ['resource/web_dashboard']),
        ('share/web_dashboard', ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='nexus',
    maintainer_email='nexus@hackathon.io',
    description='NEXUS Web Dashboard with YOLO AI Vision',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'web_server = web_dashboard.web_server:main',
        ],
    },
)
