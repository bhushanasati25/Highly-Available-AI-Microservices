from setuptools import setup, find_packages

setup(
    name="hams-common",
    version="1.0.0",
    description="Common shared utilities for Highly Available AI Microservices",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "httpx>=0.25.0",
        "structlog>=23.2.0",
        "prometheus-client>=0.19.0",
        "fastapi>=0.104.0",
        "redis>=5.0.0",
    ],
)
