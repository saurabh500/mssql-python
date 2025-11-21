"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT license.

ClientContext builder for mapping ODBC connection strings to Core TDS parameters.

This module bridges ODBC connection string conventions with the Core TDS
ClientContext structure, ensuring proper parameter mapping and defaults.
"""

from typing import Dict, Any, Optional
from mssql_python.connection_string_parser import _ConnectionStringParser


class ClientContextBuilder:
    """
    Maps ODBC connection string parameters to Core TDS ClientContext fields.
    
    This class provides the translation layer between ODBC-style connection
    strings (used by mssql-python) and the ClientContext structure expected
    by the Core TDS implementation.
    """
    
    # Mapping from ODBC parameter names (lowercase) to ClientContext field names
    PARAMETER_MAP = {
        # Server and database
        'server': 'server',
        'data source': 'server',
        'address': 'server',
        'addr': 'server',
        'network address': 'server',
        
        'database': 'database',
        'initial catalog': 'database',
        
        # Authentication
        'uid': 'user_name',
        'user id': 'user_name',
        'user': 'user_name',
        
        'pwd': 'password',
        'password': 'password',
        
        # Connection settings
        'application name': 'application_name',
        'app': 'application_name',
        
        'workstation id': 'workstation_id',
        'wsid': 'workstation_id',
        
        'connect timeout': 'connect_timeout',
        'connection timeout': 'connect_timeout',
        'timeout': 'connect_timeout',
        
        'packet size': 'packet_size',
        'packetsize': 'packet_size',
        
        # Advanced settings
        'applicationintent': 'application_intent',
        'application intent': 'application_intent',
        
        'encrypt': 'encryption',
        'encryption': 'encryption',
        
        'trustservercertificate': 'trust_server_certificate',
        'trust server certificate': 'trust_server_certificate',
        
        'multipleactiveresultsets': 'mars_enabled',
        'mars': 'mars_enabled',
        'multipleactiveresultssets': 'mars_enabled',
        
        # Add more mappings as needed
        'language': 'language',
        'failover partner': 'failover_partner',
        'attachdbfilename': 'attach_db_file',
    }
    
    @staticmethod
    def build_from_connection_string(connection_string: str) -> Dict[str, Any]:
        """
        Parse ODBC connection string and build ClientContext dictionary.
        
        Args:
            connection_string: ODBC-style connection string
            
        Returns:
            Dictionary with ClientContext fields compatible with Core TDS
            
        Example:
            >>> builder = ClientContextBuilder()
            >>> ctx = builder.build_from_connection_string(
            ...     "Server=localhost;Database=test;UID=sa;PWD=password"
            ... )
            >>> ctx['server']
            'localhost'
            >>> ctx['database']
            'test'
        """
        parser = _ConnectionStringParser(validate_keywords=True)
        odbc_params = parser._parse(connection_string)
        
        # Start with defaults
        context = ClientContextBuilder._apply_defaults()
        
        # Map ODBC parameters to ClientContext fields
        for odbc_key, value in odbc_params.items():
            if odbc_key in ClientContextBuilder.PARAMETER_MAP:
                context_key = ClientContextBuilder.PARAMETER_MAP[odbc_key]
                context[context_key] = ClientContextBuilder._convert_value(
                    context_key, value
                )
        
        return context
    
    @staticmethod
    def _apply_defaults() -> Dict[str, Any]:
        """
        Apply default values for ClientContext fields.
        
        These defaults match the Core TDS ClientContext::new() defaults
        where applicable, ensuring consistent behavior.
        
        Returns:
            Dictionary with default ClientContext values
        """
        return {
            'application_intent': 'ReadWrite',
            'application_name': 'mssql-python',
            'attach_db_file': '',
            'connect_retry_count': 0,
            'connect_timeout': 15,
            'database': '',
            'encryption': 'Optional',
            'failover_partner': '',
            'language': '',
            'mars_enabled': False,
            'packet_size': 4096,
            'password': '',
            'server': 'localhost',
            'trust_server_certificate': False,
            'user_name': '',
            'workstation_id': '',
        }
    
    @staticmethod
    def _convert_value(field: str, value: Any) -> Any:
        """
        Convert ODBC value to appropriate type for ClientContext.
        
        Handles type conversions like string "true" -> bool True,
        string numbers -> int, etc.
        
        Args:
            field: ClientContext field name
            value: Value from ODBC connection string
            
        Returns:
            Converted value with appropriate type
        """
        # Boolean fields
        if field in ('mars_enabled', 'trust_server_certificate'):
            if isinstance(value, str):
                return value.lower() in ('true', 'yes', '1', 'on')
            return bool(value)
        
        # Integer fields
        if field in ('connect_timeout', 'packet_size', 'connect_retry_count'):
            return int(value)
        
        # Encryption mapping: ODBC uses yes/no/optional/mandatory/strict
        if field == 'encryption':
            if isinstance(value, str):
                value_lower = value.lower()
                if value_lower in ('yes', 'true', '1', 'mandatory', 'strict'):
                    return 'Mandatory'
                elif value_lower in ('no', 'false', '0'):
                    return 'Disabled'
                else:
                    return 'Optional'
            return 'Optional'
        
        # ApplicationIntent mapping
        if field == 'application_intent':
            if isinstance(value, str):
                value_lower = value.lower()
                if value_lower in ('readonly', 'read-only'):
                    return 'ReadOnly'
                else:
                    return 'ReadWrite'
            return 'ReadWrite'
        
        # String fields - return as-is
        return str(value)
