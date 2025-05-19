from setuptools import setup, find_packages

setup(
    name="uav_log_viewer",
    version="0.1.0",
    description="UAV Log Viewer - Analyze and visualize UAV flight logs",
    packages=find_packages(),
    package_data={
        "uav_log_viewer": ["py.typed"],
    },
    install_requires=[
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0",
        "pydantic>=1.8.0",
        "python-dotenv>=0.19.0",
        "openai>=1.0.0",
        "pymavlink>=2.4.0",
        "numpy>=1.21.0",
        "pandas>=1.3.0",
        "python-multipart>=0.0.5",
        "sentence-transformers>=2.2.0",
        "cohere>=4.43.0"
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "uav-log-viewer=uav_log_viewer.run:main",
        ],
    },
) 