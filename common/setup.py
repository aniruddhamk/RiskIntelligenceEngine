"""
Common library for RiskIntelligenceEngine.
Shared across all microservices.
"""
from setuptools import setup, find_packages

setup(
    name="aml-common",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.0",
        "pydantic-settings>=2.0",
        "sqlalchemy>=2.0",
        "asyncpg",
        "redis>=5.0",
        "confluent-kafka>=2.3",
        "python-jose[cryptography]>=3.3",
        "passlib[bcrypt]>=1.7",
        "structlog>=24.0",
    ],
)
