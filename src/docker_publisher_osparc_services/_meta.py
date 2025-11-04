from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("docker-publisher-osparc-services")
except PackageNotFoundError:
    __version__ = "unknown"
