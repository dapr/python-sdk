from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version('dapr')
except PackageNotFoundError as e:
    raise RuntimeError(
        "dapr package metadata not found. Run 'uv sync --all-packages' or "
        "'pip install -e .' from the repo root before importing dapr."
    ) from e

__all__ = ['__version__']
