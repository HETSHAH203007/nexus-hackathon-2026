from setuptools import setup

package_name = "nexus_controller"

setup(
    name=package_name,
    version="0.0.0",
    packages=[
        package_name,
        package_name + ".controllers",
    ],
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        (
            "share/" + package_name,
            ["package.xml"],
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="het",
    maintainer_email="your@email.com",
    description="Obstacle Avoidance Controller",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "robot_controller = nexus_controller.controllers.robot_controller:main",
        ],
    },
)
