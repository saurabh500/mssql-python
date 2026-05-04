// Copyright (c) Microsoft Corporation.
// Licensed under the MIT license.
//
// crow.h - C-level Row type for mssql-python fetch hot path.
// Inspired by pyodbc's Row implementation.
// This eliminates Python __init__ overhead and list copies.

#ifndef CROW_H
#define CROW_H

#include <Python.h>
#include <pybind11/pybind11.h>

namespace py = pybind11;

// C-level Row struct — directly stores PyObject* array like pyodbc
typedef struct {
    PyObject_HEAD
    PyObject* column_map;    // dict: column_name -> index (shared, refcounted)
    PyObject** values;       // flat array of PyObject* (owned)
    Py_ssize_t num_values;   // number of columns
} CRow;

// Type object (defined in crow.cpp)
extern PyTypeObject CRowType;

// Create a new CRow taking ownership of apValues array
// column_map must be a PyDict. apValues must be PyMem_Malloc'd.
CRow* CRow_New(PyObject* column_map, Py_ssize_t num_values, PyObject** apValues);

// Initialize the CRow type (call during module init)
int CRow_Init(PyObject* module);

#endif // CROW_H
