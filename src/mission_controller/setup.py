from setuptools import find_packages, setup
setup(
    name='mission_controller',
    version='2.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index', ['resource/mission_controller']),
        ('share/mission_controller', ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='nexus',
    maintainer_email='nexus@hackathon.io',
    description='NEXUS Mission Controller with Obstacle Avoidance',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'mission_node = mission_controller.mission_node:main',
        ],
    },
)
