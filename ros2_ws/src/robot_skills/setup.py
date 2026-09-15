from setuptools import find_packages, setup

package_name = "robot_skills"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="candidate",
    maintainer_email="candidate@example.com",
    description="High-level navigation skills for the Webots RoboMaster.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "navigate_to = robot_skills.navigate_to:main",
            "follow_waypoints = robot_skills.follow_waypoints:main",
            "stop_skill = robot_skills.stop_skill:main",
        ],
    },
)
