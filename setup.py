from setuptools import setup, find_packages


def read_requirements(path="requirements.txt"):
    """Read pinned runtime requirements, ignoring comments and blank lines.

    Guards against the empty-file case: a naive read().split("\n") yields [""],
    which setuptools rejects as an invalid requirement. requirements.txt is
    currently comments only, because frappe comes from the bench rather than
    PyPI and the test dependencies live in requirements-dev.txt.
    """
    try:
        with open(path) as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return []
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


setup(
    name="ppe_tracker",
    version="0.0.1",
    description="Personal Protective Equipment lifecycle management for ERPNext",
    author="Takataka Solutions",
    author_email="info@takatakasolutions.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=read_requirements(),
)
