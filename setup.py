from setuptools import setup, find_packages

setup(
    name="aws-ops-agent",
    version="0.2.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={"ops_agent": ["dashboard/static/**/*"]},
    install_requires=[
        "boto3>=1.28.0",
        "rich>=13.0.0",
        "click>=8.0.0",
        "requests>=2.28.0",
        "fastapi>=0.100.0",
        "uvicorn>=0.23.0",
        "apscheduler>=3.10.0",
    ],
    extras_require={
        "test": [
            "pytest>=7.0",
            "hypothesis>=6.0",
            "httpx>=0.24",
            "pytest-asyncio>=0.21",
        ],
    },
    entry_points={"console_scripts": ["ops-agent=ops_agent.cli:cli"]},
    python_requires=">=3.9",
)
