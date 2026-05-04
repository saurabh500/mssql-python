// Copyright (c) Microsoft Corporation.
// Licensed under the MIT license.
//
// crow.cpp - C-level Row type implementation.
// Provides tuple-like indexing and column-name attribute access
// without Python __init__ overhead.

#include "crow.h"
#include <structmember.h>

// ─── Deallocation ───────────────────────────────────────────────────────────

static void CRow_dealloc(CRow* self) {
    Py_XDECREF(self->column_map);
    if (self->values) {
        for (Py_ssize_t i = 0; i < self->num_values; i++) {
            Py_XDECREF(self->values[i]);
        }
        PyMem_Free(self->values);
    }
    Py_TYPE(self)->tp_free((PyObject*)self);
}

// ─── Sequence protocol ──────────────────────────────────────────────────────

static Py_ssize_t CRow_length(PyObject* self) {
    return ((CRow*)self)->num_values;
}

static PyObject* CRow_item(PyObject* o, Py_ssize_t i) {
    CRow* self = (CRow*)o;
    if (i < 0 || i >= self->num_values) {
        PyErr_SetString(PyExc_IndexError, "row index out of range");
        return NULL;
    }
    PyObject* val = self->values[i];
    Py_INCREF(val);
    return val;
}

static int CRow_contains(PyObject* o, PyObject* el) {
    CRow* self = (CRow*)o;
    for (Py_ssize_t i = 0; i < self->num_values; i++) {
        int cmp = PyObject_RichCompareBool(el, self->values[i], Py_EQ);
        if (cmp != 0) return cmp;
    }
    return 0;
}

static PySequenceMethods CRow_as_sequence = {
    CRow_length,     // sq_length
    0,               // sq_concat
    0,               // sq_repeat
    CRow_item,       // sq_item
    0,               // was_sq_slice
    0,               // sq_ass_item
    0,               // sq_ass_slice
    CRow_contains,   // sq_contains
};

// ─── Mapping protocol (for row[i] with negative indices / slices) ───────────

static PyObject* CRow_subscript(PyObject* o, PyObject* key) {
    CRow* self = (CRow*)o;
    if (PyIndex_Check(key)) {
        Py_ssize_t i = PyNumber_AsSsize_t(key, PyExc_IndexError);
        if (i == -1 && PyErr_Occurred()) return 0;
        if (i < 0) i += self->num_values;
        if (i < 0 || i >= self->num_values) {
            PyErr_SetString(PyExc_IndexError, "row index out of range");
            return NULL;
        }
        Py_INCREF(self->values[i]);
        return self->values[i];
    }
    PyErr_SetString(PyExc_TypeError, "row indices must be integers");
    return NULL;
}

static PyMappingMethods CRow_as_mapping = {
    CRow_length,     // mp_length
    CRow_subscript,  // mp_subscript
    0,               // mp_ass_subscript
};

// ─── Attribute access (row.column_name) ─────────────────────────────────────

static PyObject* CRow_getattro(PyObject* o, PyObject* name) {
    CRow* self = (CRow*)o;
    if (self->column_map) {
        PyObject* index = PyDict_GetItem(self->column_map, name);
        if (index) {
            Py_ssize_t i = PyLong_AsSsize_t(index);
            if (i >= 0 && i < self->num_values) {
                Py_INCREF(self->values[i]);
                return self->values[i];
            }
        }
    }
    return PyObject_GenericGetAttr(o, name);
}

// ─── Repr ───────────────────────────────────────────────────────────────────

static PyObject* CRow_repr(PyObject* o) {
    CRow* self = (CRow*)o;
    // Build tuple for repr
    PyObject* t = PyTuple_New(self->num_values);
    if (!t) return NULL;
    for (Py_ssize_t i = 0; i < self->num_values; i++) {
        Py_INCREF(self->values[i]);
        PyTuple_SET_ITEM(t, i, self->values[i]);
    }
    PyObject* result = PyObject_Repr(t);
    Py_DECREF(t);
    return result;
}

// ─── Iterator ───────────────────────────────────────────────────────────────

typedef struct {
    PyObject_HEAD
    CRow* row;
    Py_ssize_t index;
} CRowIter;

static void CRowIter_dealloc(CRowIter* self) {
    Py_XDECREF((PyObject*)self->row);
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject* CRowIter_next(CRowIter* self) {
    if (self->index >= self->row->num_values) return NULL;
    PyObject* val = self->row->values[self->index++];
    Py_INCREF(val);
    return val;
}

static PyTypeObject CRowIterType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "mssql_python.CRowIterator",
    sizeof(CRowIter),
    0,
    (destructor)CRowIter_dealloc,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    Py_TPFLAGS_DEFAULT,
    0, 0, 0, 0, 0,
    PyObject_SelfIter,
    (iternextfunc)CRowIter_next,
};

static PyObject* CRow_iter(PyObject* o) {
    CRow* self = (CRow*)o;
    CRowIter* it = PyObject_New(CRowIter, &CRowIterType);
    if (!it) return NULL;
    Py_INCREF(self);
    it->row = self;
    it->index = 0;
    return (PyObject*)it;
}

// ─── Equality ───────────────────────────────────────────────────────────────

static PyObject* CRow_richcompare(PyObject* olhs, PyObject* orhs, int op) {
    if (op != Py_EQ && op != Py_NE) {
        Py_RETURN_NOTIMPLEMENTED;
    }
    // Support comparison with list/tuple
    CRow* lhs = (CRow*)olhs;
    Py_ssize_t rhs_len = -1;
    
    if (PyList_Check(orhs)) rhs_len = PyList_GET_SIZE(orhs);
    else if (PyTuple_Check(orhs)) rhs_len = PyTuple_GET_SIZE(orhs);
    else if (Py_TYPE(orhs) == &CRowType) rhs_len = ((CRow*)orhs)->num_values;
    else Py_RETURN_NOTIMPLEMENTED;

    if (lhs->num_values != rhs_len) {
        if (op == Py_EQ) Py_RETURN_FALSE;
        Py_RETURN_TRUE;
    }

    for (Py_ssize_t i = 0; i < lhs->num_values; i++) {
        PyObject* rv;
        if (PyList_Check(orhs)) rv = PyList_GET_ITEM(orhs, i);
        else if (PyTuple_Check(orhs)) rv = PyTuple_GET_ITEM(orhs, i);
        else rv = ((CRow*)orhs)->values[i];
        
        int eq = PyObject_RichCompareBool(lhs->values[i], rv, Py_EQ);
        if (eq < 0) return NULL;
        if (!eq) {
            if (op == Py_EQ) Py_RETURN_FALSE;
            Py_RETURN_TRUE;
        }
    }
    if (op == Py_EQ) Py_RETURN_TRUE;
    Py_RETURN_FALSE;
}

// ─── Type definition ────────────────────────────────────────────────────────

PyTypeObject CRowType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "mssql_python.CRow",           // tp_name
    sizeof(CRow),                   // tp_basicsize
    0,                              // tp_itemsize
    (destructor)CRow_dealloc,       // tp_dealloc
    0,                              // tp_vectorcall_offset
    0,                              // tp_getattr
    0,                              // tp_setattr
    0,                              // tp_as_async
    CRow_repr,                      // tp_repr
    0,                              // tp_as_number
    &CRow_as_sequence,              // tp_as_sequence
    &CRow_as_mapping,               // tp_as_mapping
    0,                              // tp_hash
    0,                              // tp_call
    0,                              // tp_str
    CRow_getattro,                  // tp_getattro
    0,                              // tp_setattro
    0,                              // tp_as_buffer
    Py_TPFLAGS_DEFAULT,             // tp_flags
    "C-level Row for mssql-python", // tp_doc
    0,                              // tp_traverse
    0,                              // tp_clear
    CRow_richcompare,               // tp_richcompare
    0,                              // tp_weaklistoffset
    CRow_iter,                      // tp_iter
    0,                              // tp_iternext
    0,                              // tp_methods
    0,                              // tp_members
    0,                              // tp_getset
    0,                              // tp_base
    0,                              // tp_dict
    0,                              // tp_descr_get
    0,                              // tp_descr_set
    0,                              // tp_dictoffset
    0,                              // tp_init
    0,                              // tp_alloc
    0,                              // tp_new (not user-constructible)
};

// ─── Factory function ───────────────────────────────────────────────────────

CRow* CRow_New(PyObject* column_map, Py_ssize_t num_values, PyObject** apValues) {
    CRow* row = PyObject_New(CRow, &CRowType);
    if (!row) {
        // Free values on failure
        for (Py_ssize_t i = 0; i < num_values; i++) Py_XDECREF(apValues[i]);
        PyMem_Free(apValues);
        return NULL;
    }
    Py_XINCREF(column_map);
    row->column_map = column_map;
    row->values = apValues;
    row->num_values = num_values;
    return row;
}

// ─── Module init ────────────────────────────────────────────────────────────

int CRow_Init(PyObject* module) {
    if (PyType_Ready(&CRowType) < 0) return -1;
    if (PyType_Ready(&CRowIterType) < 0) return -1;
    Py_INCREF(&CRowType);
    if (PyModule_AddObject(module, "CRow", (PyObject*)&CRowType) < 0) {
        Py_DECREF(&CRowType);
        return -1;
    }
    return 0;
}
