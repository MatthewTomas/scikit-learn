"""Tests for input validation functions"""

from tempfile import NamedTemporaryFile
import numpy as np
from numpy.testing import assert_array_equal, assert_warns
import scipy.sparse as sp
from nose.tools import assert_raises, assert_true, assert_false, assert_equal
from itertools import product

from sklearn.utils import as_float_array, check_array, check_symmetric
from sklearn.utils import check_X_y

from sklearn.utils.estimator_checks import NotAnArray

from sklearn.random_projection import sparse_random_matrix

from sklearn.linear_model import ARDRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import RandomForestRegressor
from sklearn.svm import SVR

from sklearn.datasets import make_blobs
from sklearn.utils.validation import (
    NotFittedError,
    has_fit_parameter,
    check_is_fitted)

from sklearn.utils.testing import assert_raise_message


def test_as_float_array():
    """Test function for as_float_array"""
    X = np.ones((3, 10), dtype=np.int32)
    X = X + np.arange(10, dtype=np.int32)
    # Checks that the return type is ok
    X2 = as_float_array(X, copy=False)
    np.testing.assert_equal(X2.dtype, np.float32)
    # Another test
    X = X.astype(np.int64)
    X2 = as_float_array(X, copy=True)
    # Checking that the array wasn't overwritten
    assert_true(as_float_array(X, False) is not X)
    # Checking that the new type is ok
    np.testing.assert_equal(X2.dtype, np.float64)
    # Here, X is of the right type, it shouldn't be modified
    X = np.ones((3, 2), dtype=np.float32)
    assert_true(as_float_array(X, copy=False) is X)
    # Test that if X is fortran ordered it stays
    X = np.asfortranarray(X)
    assert_true(np.isfortran(as_float_array(X, copy=True)))

    # Test the copy parameter with some matrices
    matrices = [
        np.matrix(np.arange(5)),
        sp.csc_matrix(np.arange(5)).toarray(),
        sparse_random_matrix(10, 10, density=0.10).toarray()
    ]
    for M in matrices:
        N = as_float_array(M, copy=True)
        N[0, 0] = np.nan
        assert_false(np.isnan(M).any())


def test_np_matrix():
    """Confirm that input validation code does not return np.matrix"""
    X = np.arange(12).reshape(3, 4)

    assert_false(isinstance(as_float_array(X), np.matrix))
    assert_false(isinstance(as_float_array(np.matrix(X)), np.matrix))
    assert_false(isinstance(as_float_array(sp.csc_matrix(X)), np.matrix))


def test_memmap():
    """Confirm that input validation code doesn't copy memory mapped arrays"""

    asflt = lambda x: as_float_array(x, copy=False)

    with NamedTemporaryFile(prefix='sklearn-test') as tmp:
        M = np.memmap(tmp, shape=100, dtype=np.float32)
        M[:] = 0

        for f in (check_array, np.asarray, asflt):
            X = f(M)
            X[:] = 1
            assert_array_equal(X.ravel(), M)
            X[:] = 0


def test_ordering():
    """Check that ordering is enforced correctly by validation utilities.

    We need to check each validation utility, because a 'copy' without
    'order=K' will kill the ordering.
    """
    X = np.ones((10, 5))
    for A in X, X.T:
        for copy in (True, False):
            B = check_array(A, order='C', copy=copy)
            assert_true(B.flags['C_CONTIGUOUS'])
            B = check_array(A, order='F', copy=copy)
            assert_true(B.flags['F_CONTIGUOUS'])
            if copy:
                assert_false(A is B)

    X = sp.csr_matrix(X)
    X.data = X.data[::-1]
    assert_false(X.data.flags['C_CONTIGUOUS'])

    for copy in (True, False):
        Y = check_array(X, accept_sparse='csr', copy=copy, order='C')
        assert_true(Y.data.flags['C_CONTIGUOUS'])


def test_check_array():
    # accept_sparse == None
    # raise error on sparse inputs
    X = [[1, 2], [3, 4]]
    X_csr = sp.csr_matrix(X)
    assert_raises(TypeError, check_array, X_csr)
    # ensure_2d
    X_array = check_array([0, 1, 2])
    assert_equal(X_array.ndim, 2)
    X_array = check_array([0, 1, 2], ensure_2d=False)
    assert_equal(X_array.ndim, 1)
    # don't allow ndim > 3
    X_ndim = np.arange(8).reshape(2, 2, 2)
    assert_raises(ValueError, check_array, X_ndim)
    check_array(X_ndim, allow_nd=True)  # doesn't raise
    # force_all_finite
    X_inf = np.arange(4).reshape(2, 2).astype(np.float)
    X_inf[0, 0] = np.inf
    assert_raises(ValueError, check_array, X_inf)
    check_array(X_inf, force_all_finite=False)  # no raise
    # nan check
    X_nan = np.arange(4).reshape(2, 2).astype(np.float)
    X_nan[0, 0] = np.nan
    assert_raises(ValueError, check_array, X_nan)
    check_array(X_inf, force_all_finite=False)  # no raise

    # dtype and order enforcement.
    X_C = np.arange(4).reshape(2, 2).copy("C")
    X_F = X_C.copy("F")
    X_int = X_C.astype(np.int)
    X_float = X_C.astype(np.float)
    Xs = [X_C, X_F, X_int, X_float]
    dtypes = [np.int32, np.int, np.float, np.float32, None, np.bool, object]
    orders = ['C', 'F', None]
    copys = [True, False]

    for X, dtype, order, copy in product(Xs, dtypes, orders, copys):
        X_checked = check_array(X, dtype=dtype, order=order, copy=copy)
        if dtype is not None:
            assert_equal(X_checked.dtype, dtype)
        else:
            assert_equal(X_checked.dtype, X.dtype)
        if order == 'C':
            assert_true(X_checked.flags['C_CONTIGUOUS'])
            assert_false(X_checked.flags['F_CONTIGUOUS'])
        elif order == 'F':
            assert_true(X_checked.flags['F_CONTIGUOUS'])
            assert_false(X_checked.flags['C_CONTIGUOUS'])
        if copy:
            assert_false(X is X_checked)
        else:
            # doesn't copy if it was already good
            if (X.dtype == X_checked.dtype and
                    X_checked.flags['C_CONTIGUOUS'] == X.flags['C_CONTIGUOUS']
                    and X_checked.flags['F_CONTIGUOUS'] == X.flags['F_CONTIGUOUS']):
                assert_true(X is X_checked)

    # allowed sparse != None
    X_csc = sp.csc_matrix(X_C)
    X_coo = X_csc.tocoo()
    X_dok = X_csc.todok()
    X_int = X_csc.astype(np.int)
    X_float = X_csc.astype(np.float)

    Xs = [X_csc, X_coo, X_dok, X_int, X_float]
    accept_sparses = [['csr', 'coo'], ['coo', 'dok']]
    for X, dtype, accept_sparse, copy in product(Xs, dtypes, accept_sparses,
                                                 copys):
        X_checked = check_array(X, dtype=dtype, accept_sparse=accept_sparse,
                                copy=copy)
        if dtype is not None:
            assert_equal(X_checked.dtype, dtype)
        else:
            assert_equal(X_checked.dtype, X.dtype)
        if X.format in accept_sparse:
            # no change if allowed
            assert_equal(X.format, X_checked.format)
        else:
            # got converted
            assert_equal(X_checked.format, accept_sparse[0])
        if copy:
            assert_false(X is X_checked)
        else:
            # doesn't copy if it was already good
            if (X.dtype == X_checked.dtype and X.format == X_checked.format):
                assert_true(X is X_checked)

    # other input formats
    # convert lists to arrays
    X_dense = check_array([[1, 2], [3, 4]])
    assert_true(isinstance(X_dense, np.ndarray))
    # raise on too deep lists
    assert_raises(ValueError, check_array, X_ndim.tolist())
    check_array(X_ndim.tolist(), allow_nd=True)  # doesn't raise
    # convert weird stuff to arrays
    X_no_array = NotAnArray(X_dense)
    result = check_array(X_no_array)
    assert_true(isinstance(result, np.ndarray))


def test_check_array_min_samples_and_features_messages():
    # empty list is considered 2D by default:
    msg = "0 feature(s) (shape=(1, 0)) while a minimum of 1 is required."
    assert_raise_message(ValueError, msg, check_array, [])

    # If considered a 1D collection when ensure_2d=False, then the minimum
    # number of samples will break:
    msg = "0 sample(s) (shape=(0,)) while a minimum of 1 is required."
    assert_raise_message(ValueError, msg, check_array, [], ensure_2d=False)

    # Invalid edge case when checking the default minimum sample of a scalar
    msg = "Singleton array array(42) cannot be considered a valid collection."
    assert_raise_message(TypeError, msg, check_array, 42, ensure_2d=False)

    # But this works if the input data is forced to look like a 2 array with
    # one sample and one feature:
    X_checked = check_array(42, ensure_2d=True)
    assert_array_equal(np.array([[42]]), X_checked)

    # Simulate a model that would need at least 2 samples to be well defined
    X = np.ones((1, 10))
    y = np.ones(1)
    msg = "1 sample(s) (shape=(1, 10)) while a minimum of 2 is required."
    assert_raise_message(ValueError, msg, check_X_y, X, y,
                         ensure_min_samples=2)

    # Simulate a model that would require at least 3 features (e.g. SelectKBest
    # with k=3)
    X = np.ones((10, 2))
    y = np.ones(2)
    msg = "2 feature(s) (shape=(10, 2)) while a minimum of 3 is required."
    assert_raise_message(ValueError, msg, check_X_y, X, y,
                         ensure_min_features=3)

    # Simulate a case where a pipeline stage as trimmed all the features of a
    # 2D dataset.
    X = np.empty(0).reshape(10, 0)
    y = np.ones(10)
    msg = "0 feature(s) (shape=(10, 0)) while a minimum of 1 is required."
    assert_raise_message(ValueError, msg, check_X_y, X, y)

    # nd-data is not checked for any minimum number of features by default:
    X = np.ones((10, 0, 28, 28))
    y = np.ones(10)
    X_checked, y_checked = check_X_y(X, y, allow_nd=True)
    assert_array_equal(X, X_checked)
    assert_array_equal(y, y_checked)


def test_has_fit_parameter():
    assert_false(has_fit_parameter(KNeighborsClassifier, "sample_weight"))
    assert_true(has_fit_parameter(RandomForestRegressor, "sample_weight"))
    assert_true(has_fit_parameter(SVR, "sample_weight"))
    assert_true(has_fit_parameter(SVR(), "sample_weight"))


def test_check_symmetric():
    arr_sym = np.array([[0, 1], [1, 2]])
    arr_bad = np.ones(2)
    arr_asym = np.array([[0, 2], [0, 2]])

    test_arrays = {'dense': arr_asym,
                   'dok': sp.dok_matrix(arr_asym),
                   'csr': sp.csr_matrix(arr_asym),
                   'csc': sp.csc_matrix(arr_asym),
                   'coo': sp.coo_matrix(arr_asym),
                   'lil': sp.lil_matrix(arr_asym),
                   'bsr': sp.bsr_matrix(arr_asym)}

    # check error for bad inputs
    assert_raises(ValueError, check_symmetric, arr_bad)

    # check that asymmetric arrays are properly symmetrized
    for arr_format, arr in test_arrays.items():
        # Check for warnings and errors
        assert_warns(UserWarning, check_symmetric, arr)
        assert_raises(ValueError, check_symmetric, arr, raise_exception=True)

        output = check_symmetric(arr, raise_warning=False)
        if sp.issparse(output):
            assert_equal(output.format, arr_format)
            assert_array_equal(output.toarray(), arr_sym)
        else:
            assert_array_equal(output, arr_sym)


def test_check_is_fitted():
    # Check is ValueError raised when non estimator instance passed
    assert_raises(ValueError, check_is_fitted, ARDRegression, "coef_")
    assert_raises(ValueError, check_is_fitted, "SVR", "support_")

    ard = ARDRegression()
    svr = SVR()

    try:
        assert_raises(NotFittedError, check_is_fitted, ard, "coef_")
        assert_raises(NotFittedError, check_is_fitted, svr, "support_")
    except ValueError:
        assert False, "check_is_fitted failed with ValueError"

    # NotFittedError is a subclass of both ValueError and AttributeError
    try:
        check_is_fitted(ard, "coef_", "Random message %(name)s, %(name)s")
    except ValueError as e:
        assert_equal(str(e), "Random message ARDRegression, ARDRegression")

    try:
        check_is_fitted(svr, "support_", "Another message %(name)s, %(name)s")
    except AttributeError as e:
        assert_equal(str(e), "Another message SVR, SVR")

    ard.fit(*make_blobs())
    svr.fit(*make_blobs())

    assert_equal(None, check_is_fitted(ard, "coef_"))
    assert_equal(None, check_is_fitted(svr, "support_"))
