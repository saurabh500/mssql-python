"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT license.

Backend configuration module for mssql-python.

Provides module-level configuration to select between ODBC and Core TDS backends.
"""

import os
from typing import Literal

BackendType = Literal['odbc', 'core']

# Module-level backend configuration
_backend: BackendType = 'odbc'  # Default to ODBC for backward compatibility


def set_backend(backend: BackendType) -> None:
    """
    Set the backend to use for new connections.
    
    Args:
        backend: 'odbc' or 'core'
        
    Raises:
        ValueError: If backend is not valid
        
    Examples:
        >>> import mssql_python
        >>> from mssql_python.backend_config import set_backend
        >>> set_backend('core')  # Use Core TDS backend
        >>> conn = mssql_python.connect("Server=localhost;...")
    """
    global _backend
    if backend not in ('odbc', 'core'):
        raise ValueError(f"Invalid backend: {backend}. Must be 'odbc' or 'core'")
    _backend = backend


def get_backend() -> BackendType:
    """
    Get the current backend setting.
    
    Returns:
        Current backend ('odbc' or 'core')
        
    Note:
        Environment variable MSSQL_PYTHON_BACKEND takes precedence over
        the module-level setting if set.
        
    Examples:
        >>> from mssql_python.backend_config import get_backend
        >>> backend = get_backend()
        >>> print(f"Using backend: {backend}")
    """
    # Check environment variable first (takes precedence)
    env_backend = os.getenv('MSSQL_PYTHON_BACKEND', '').lower()
    if env_backend in ('odbc', 'core'):
        return env_backend  # type: ignore
    return _backend


def reset_backend() -> None:
    """
    Reset backend to default (ODBC).
    
    This is primarily useful for testing purposes to ensure
    a clean state between test runs.
    
    Examples:
        >>> from mssql_python.backend_config import set_backend, reset_backend
        >>> set_backend('core')
        >>> reset_backend()  # Back to 'odbc'
    """
    global _backend
    _backend = 'odbc'
