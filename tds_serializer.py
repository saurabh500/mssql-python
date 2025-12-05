"""
TDS Wire Format Serializer for Python

Directly serializes Python types to TDS wire format bytes, eliminating Rust conversion overhead.

TDS Wire Format Reference (for bulk copy ROW tokens):
- NULL: 0xFF 0xFF (VARNULL for variable-length types)
- INT (INTN): 0x04 (length) + 4 bytes little-endian
- BIGINT (INTN): 0x08 (length) + 8 bytes little-endian
- BIT (BITN): 0x01 (length) + 1 byte (0x00 or 0x01)
- FLOAT (FLTN): 0x08 (length) + 8 bytes little-endian double
- NVARCHAR: 2-byte length (little-endian) + UTF-16LE bytes
- DATETIME: 8 bytes (4 bytes days since 1900-01-01 + 4 bytes time)
- DATE: 3 bytes (days since 0001-01-01, little-endian)
- BOOL: Same as BIT

Performance Strategy:
- Use struct.pack for binary encoding (faster than manual byte manipulation)
- Pre-allocate bytearray buffers sized for expected row data
- UTF-16LE encoding via str.encode('utf-16le') (optimized C code)
- Minimize object allocations
"""

import struct
from datetime import datetime, date, time
from typing import Any, Optional, List
from io import BytesIO


class TdsSerializer:
    """
    Serializes Python row data directly to TDS wire format bytes.
    
    This eliminates the need for Rust-side type conversion by pre-serializing
    all values to the exact byte format expected by SQL Server.
    """
    
    def __init__(self, column_types: List[str]):
        """
        Initialize serializer with column type information.
        
        Args:
            column_types: List of TDS type names for each column.
                Supported: 'INT', 'BIGINT', 'NVARCHAR', 'BIT', 'FLOAT', 
                          'DATE', 'DATETIME', 'NULL'
        """
        self.column_types = column_types
        self.num_columns = len(column_types)
        
        # Pre-compile struct formatters for performance
        self._int_struct = struct.Struct('<I')      # 4-byte little-endian unsigned
        self._bigint_struct = struct.Struct('<q')   # 8-byte little-endian signed
        self._float_struct = struct.Struct('<d')    # 8-byte little-endian double
        self._short_struct = struct.Struct('<H')    # 2-byte little-endian unsigned
        
        # Common NULL marker (0xFF 0xFF for variable-length types)
        self.VARNULL = b'\xFF\xFF'
        
    def serialize_row(self, row: List[Any]) -> bytes:
        """
        Serialize a single row to TDS wire format.
        
        Args:
            row: List of Python values matching column_types
            
        Returns:
            TDS wire format bytes for this row (without ROW token)
        """
        if len(row) != self.num_columns:
            raise ValueError(
                f"Row has {len(row)} values but {self.num_columns} columns expected"
            )
        
        # Use BytesIO for efficient byte concatenation
        buffer = BytesIO()
        
        for value, col_type in zip(row, self.column_types):
            if value is None:
                # NULL serialization depends on type
                if col_type in ('INT', 'BIGINT', 'BIT', 'FLOAT'):
                    buffer.write(b'\x00')  # NULL_LENGTH for nullable int types
                else:
                    buffer.write(self.VARNULL)  # VARNULL for variable-length
            elif col_type == 'INT':
                buffer.write(self._serialize_int(value))
            elif col_type == 'BIGINT':
                buffer.write(self._serialize_bigint(value))
            elif col_type == 'BIT':
                buffer.write(self._serialize_bit(value))
            elif col_type == 'FLOAT':
                buffer.write(self._serialize_float(value))
            elif col_type == 'NVARCHAR':
                buffer.write(self._serialize_nvarchar(value))
            elif col_type == 'DATE':
                buffer.write(self._serialize_date(value))
            elif col_type == 'DATETIME':
                buffer.write(self._serialize_datetime(value))
            else:
                raise ValueError(f"Unsupported column type: {col_type}")
        
        return buffer.getvalue()
    
    def _serialize_int(self, value: int) -> bytes:
        """Serialize INT (INTN with length prefix)"""
        # INTN format: 0x04 (length) + 4 bytes little-endian
        return b'\x04' + self._int_struct.pack(value)
    
    def _serialize_bigint(self, value: int) -> bytes:
        """Serialize BIGINT (INTN with length prefix)"""
        # INTN format: 0x08 (length) + 8 bytes little-endian
        return b'\x08' + self._bigint_struct.pack(value)
    
    def _serialize_bit(self, value: bool) -> bytes:
        """Serialize BIT (BITN with length prefix)"""
        # BITN format: 0x01 (length) + 1 byte (0 or 1)
        byte_val = 1 if value else 0
        return b'\x01' + bytes([byte_val])
    
    def _serialize_float(self, value: float) -> bytes:
        """Serialize FLOAT (FLTN with length prefix)"""
        # FLTN format: 0x08 (length) + 8 bytes little-endian double
        return b'\x08' + self._float_struct.pack(value)
    
    def _serialize_nvarchar(self, value: str) -> bytes:
        """Serialize NVARCHAR (2-byte length + UTF-16LE bytes)"""
        # Encode to UTF-16LE (SQL Server's native encoding)
        utf16_bytes = value.encode('utf-16le')
        length = len(utf16_bytes)
        
        # Write 2-byte length prefix + UTF-16LE bytes
        return self._short_struct.pack(length) + utf16_bytes
    
    def _serialize_date(self, value: date) -> bytes:
        """Serialize DATE (3 bytes, days since 0001-01-01)"""
        # Calculate days since 0001-01-01
        epoch = date(1, 1, 1)
        days_since_epoch = (value - epoch).days
        
        # Pack as 3-byte little-endian (write 4 bytes, take first 3)
        packed = struct.pack('<I', days_since_epoch)
        return b'\x03' + packed[:3]  # Length prefix + 3 bytes
    
    def _serialize_datetime(self, value: datetime) -> bytes:
        """Serialize DATETIME (8 bytes: 4 bytes days + 4 bytes time)"""
        # SQL Server DATETIME format:
        # - Days since 1900-01-01 (4 bytes, signed)
        # - Time as 1/300th of a second since midnight (4 bytes, signed)
        
        epoch = datetime(1900, 1, 1)
        delta = value - epoch
        
        days = delta.days
        seconds = delta.seconds + (delta.microseconds / 1_000_000)
        time_ticks = int(seconds * 300)  # Convert to 1/300th of a second
        
        # Pack as 8 bytes: days (4 bytes) + time (4 bytes)
        return b'\x08' + struct.pack('<ii', days, time_ticks)


class TdsRowBuffer:
    """
    High-performance buffer for serializing multiple rows.
    
    Pre-allocates memory and reuses buffers to minimize allocations.
    """
    
    def __init__(self, serializer: TdsSerializer, initial_capacity: int = 4096):
        """
        Initialize row buffer.
        
        Args:
            serializer: TdsSerializer instance
            initial_capacity: Initial buffer size in bytes
        """
        self.serializer = serializer
        self.buffer = bytearray(initial_capacity)
        self.position = 0
        
    def add_row(self, row: List[Any]) -> None:
        """Add a serialized row to the buffer"""
        row_bytes = self.serializer.serialize_row(row)
        row_len = len(row_bytes)
        
        # Ensure capacity
        if self.position + row_len > len(self.buffer):
            # Grow buffer by 2x or enough for this row
            new_size = max(len(self.buffer) * 2, self.position + row_len)
            self.buffer.extend(bytearray(new_size - len(self.buffer)))
        
        # Copy row bytes to buffer
        self.buffer[self.position:self.position + row_len] = row_bytes
        self.position += row_len
    
    def get_bytes(self) -> bytes:
        """Get serialized bytes for all rows"""
        return bytes(self.buffer[:self.position])
    
    def clear(self) -> None:
        """Reset buffer for reuse"""
        self.position = 0


# Example usage
if __name__ == "__main__":
    # Define schema
    column_types = ['INT', 'NVARCHAR', 'BIT', 'FLOAT']
    serializer = TdsSerializer(column_types)
    
    # Serialize a single row
    row = [42, "Hello, SQL Server!", True, 3.14159]
    tds_bytes = serializer.serialize_row(row)
    print(f"Serialized {len(row)} columns to {len(tds_bytes)} bytes")
    print(f"Hex: {tds_bytes.hex()}")
    
    # Serialize multiple rows with buffer
    buffer = TdsRowBuffer(serializer)
    for i in range(3):
        row = [i, f"Row {i}", i % 2 == 0, i * 1.5]
        buffer.add_row(row)
    
    all_bytes = buffer.get_bytes()
    print(f"\nSerialized 3 rows to {len(all_bytes)} bytes")
