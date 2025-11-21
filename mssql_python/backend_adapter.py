"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT license.

Backend adapter for routing connections between ODBC and Core TDS backends.

This module provides the abstraction layer that routes connection creation
based on the configured backend (ODBC or Core TDS). It handles the different
requirements of each backend:

- ODBC backend: Receives connection string directly
- Core backend: Receives connection string, maps to ClientContext, passes to Core TDS

The adapter ensures a consistent interface regardless of the underlying backend.
"""

from typing import Protocol, Union, Dict, Any
from mssql_python import ddbc_bindings
from mssql_python.backend_config import get_backend
from mssql_python.client_context_builder import ClientContextBuilder

# Try to import Core TDS backend (may not be installed)
try:
    from mssql_core_tds import DdbcConnection as CoreDdbcConnection
    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False
    CoreDdbcConnection = None


class BackendConnection(Protocol):
    """
    Protocol defining the interface that all backend connections must implement.
    
    This ensures that both ODBC and Core backends provide a consistent API
    to the Connection class, enabling transparent backend switching.
    """
    
    def close(self) -> None:
        """Close the connection."""
        ...
    
    def cursor(self):
        """Create and return a cursor object."""
        ...
    
    def commit(self) -> None:
        """Commit the current transaction."""
        ...
    
    def rollback(self) -> None:
        """Roll back the current transaction."""
        ...


class BackendAdapter:
    """
    Factory for creating backend-specific connections.
    
    This adapter implements the routing logic that directs connection creation
    to the appropriate backend based on module-level configuration. It also
    handles the translation layer for the Core backend (ODBC connection string
    to ClientContext).
    
    Architecture:
        ┌─────────────────────────────────────┐
        │       Connection (DB-API 2.0)       │
        └─────────────────┬───────────────────┘
                          │
                          v
        ┌─────────────────────────────────────┐
        │       BackendAdapter.create()       │
        └─────────────────┬───────────────────┘
                          │
            ┌─────────────┴──────────────┐
            v                             v
    ┌───────────────┐           ┌────────────────┐
    │ ODBC Backend  │           │  Core Backend  │
    │ (ddbc_bindings│           │ (mssql_core_tds│
    │  .Connection) │           │ .DdbcConnection│
    └───────────────┘           └────────────────┘
            │                             │
            v                             v
    Uses connection         Maps to ClientContext
    string directly         then connects
    
    Example:
        >>> from mssql_python.backend_adapter import BackendAdapter
        >>> from mssql_python import backend_config
        >>> 
        >>> # Use ODBC backend (default)
        >>> conn = BackendAdapter.create_connection("Server=localhost;...")
        >>> 
        >>> # Switch to Core backend
        >>> backend_config.set_backend('core')
        >>> conn = BackendAdapter.create_connection("Server=localhost;...")
    """
    
    @staticmethod
    def create_connection(connection_string: str, **kwargs) -> BackendConnection:
        """
        Create a connection using the configured backend.
        
        This method examines the current backend configuration and routes
        the connection creation accordingly:
        
        - For 'odbc': Creates ddbc_bindings.Connection directly with the
          connection string
        - For 'core': Parses the connection string into ClientContext
          parameters and creates a Core TDS connection
        
        Args:
            connection_string: ODBC-style connection string (used for both backends)
            **kwargs: Additional connection parameters (passed through to backend)
            
        Returns:
            Backend-specific connection object implementing BackendConnection protocol
            
        Raises:
            ImportError: If Core backend is selected but mssql_core_tds is not installed
            
        Example:
            >>> # ODBC backend (default)
            >>> conn = BackendAdapter.create_connection(
            ...     "Server=localhost;Database=test;Trusted_Connection=yes"
            ... )
            >>> 
            >>> # Core backend
            >>> import mssql_python
            >>> mssql_python.set_backend('core')
            >>> conn = BackendAdapter.create_connection(
            ...     "Server=localhost;Database=test;UID=sa;PWD=password"
            ... )
        """
        backend = get_backend()
        
        if backend == 'core':
            # Core TDS backend - map connection string to ClientContext
            if not CORE_AVAILABLE:
                raise ImportError(
                    "Core TDS backend not available. "
                    "The mssql_core_tds module is not installed. "
                    "Install with: pip install mssql-python[core]"
                )
            
            # Parse ODBC connection string and map to ClientContext fields
            client_context = ClientContextBuilder.build_from_connection_string(
                connection_string
            )
            
            # Pass ClientContext dictionary to Core TDS connection
            # The PyO3 layer will receive this as a Python dict and convert
            # it to the Rust ClientContext structure
            return CoreDdbcConnection(client_context, **kwargs)  # type: ignore
            
        else:
            # ODBC backend (default) - pass connection string directly
            return ddbc_bindings.Connection(connection_string, **kwargs)
