# CSC453 Midterm Blog Post
## Table of Content

- [Topic](#topic)
- [Example Python code](#example-python-code)
- [Purpose](#purpose)
- [Execution](#execution)
  - [MAKE_FUNCTION](#make_function)
  - [CALL_FUNCTION](#call_function)

## Topic
Calling a function with some integer arguments and having that function return an integer.

## Example Python code
Now, let's start with the following code snippet **test.py**:
```Python
def foo(intnum):
	return intnum
foo(5)
```
If we compile this file in Python 2.7.8:
```Python
>>> test_obj = compile(open('test.py').read(), 'test.py', 'exec')
```
we can get a code object _test_obj_ represent the compiled code from **test.py**. The the bytecode is stored in
```Python
>>> test_obj.co_code
'd\x00\x00\x84\x00\x00Z\x00\x00e\x00\x00d\x01\x00\x83\x01\x00\x01d\x02\x00S'
```
The human-friendly disassambled bytecode is:
```Python
  1           0 LOAD_CONST               0 (<code object foo at 0x1004b9830, file "test.py", line 1>)
              3 MAKE_FUNCTION            0
              6 STORE_NAME               0 (foo)

  3           9 LOAD_NAME                0 (foo)
             12 LOAD_CONST               1 (5)
             15 CALL_FUNCTION            1
             18 POP_TOP
             19 LOAD_CONST               2 (None)
             22 RETURN_VALUE
```

## Purpose
Via this example we want to go through how user-defined funtions work in the interpreter.
So the Highlight part should be [`MAKE_FUNCTION`](#make_function) and [`CALL_FUNCTION`](#call_function)

## Execution
1.In the main loop of the interpreter, it will simply load the code object (`LOAD_CONST`) which is stored in
```Python
>>> test_obj.co_consts
(<code object foo at 0x1004b9830, file "test.py", line 1>, 5, None)
```
Note the code object we load here is different from _test_obj_.
Let's call it _foo_obj_:
```Python
>>> foo_obj = test_obj.co_consts[0]
>>> foo_obj
<code object foo at 0x1005b9830, file "test.py", line 1>
```
The disassbly of the code is:
```Python
  2           0 LOAD_FAST                0 (intnum)
              3 RETURN_VALUE
```
Then, Python will create a function object (`MAKE_FUNCTION`) and bind it to the name _foo_ in _co_names_ and push it into the value stack(`STORE_NAME`).
```Python
>>> test_obj.co_names
('foo',)
```
Lets dive into the [`MAKE_FUNCTION`](#make_function)

### MAKE_FUNCTION
Here's the code in the iterpreter:
```C
//ceval.c
...
case MAKE_FUNCTION:
            v = POP(); /* code object */
            x = PyFunction_New(v, f->f_globals);
            ...
            PUSH(x);
            break;
...
```
In the main interpreter loop, it will call `PyFunction_New` with _foo_obj_ and the _globals_ of the current frame.
```C
//funcobject.c: PyFunction_New(PyObject *code, PyObject *globals) *reference count related code are omited here
PyFunctionObject *op = PyObject_GC_New(PyFunctionObject,&PyFunction_Type);
static PyObject *__name__ = 0;
if (op != NULL) {
    ...
    op->func_code = code;// CSC253: assign code
    op->func_globals = globals;// CSC253: copy globals
    op->func_name = ((PyCodeObject *)code)->co_name;// CSC253: copy function name
    op->func_defaults = NULL; /* No default arguments */
    op->func_closure = NULL;
    consts = ((PyCodeObject *)code)->co_consts;// CSC253: copy constants
    ...
}
...
return (PyObject *)op;
```
Here, `PyFunction_New` will grab the code we got from _foo_obj_ and fill it into our new PyFuntionObject _op_, then copy the function name _foo_ which is stored in _foo_obj_'s _co_name_, as well as the constants stored in _foo_obj_'s _co_consts_
After some checks which are unimportant here. This function call will return _op_ and the interpreter will push it into the value stack
### CALL_FUNCTION