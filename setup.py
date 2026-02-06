"""
Newsnack Data Collection & Processing Package Setup
"""
from setuptools import setup, find_packages

# requirements.txt에서 의존성 읽기
with open("requirements.txt", encoding="utf-8") as f:
    requirements = [
        line.strip()
        for line in f
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="newsnack-data",
    version="0.1.0",
    description="뉴스 수집 및 이슈 클러스터링 자동화 시스템",
    author="newsnack",
    python_requires=">=3.8",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=requirements,
    zip_safe=False,
)
