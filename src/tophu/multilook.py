import warnings
from typing import Iterable, SupportsInt, Tuple, Union, cast

import dask.array as da
import numpy as np

from . import util

__all__ = [
    "multilook",
]


IntOrInts = Union[SupportsInt, Iterable[SupportsInt]]


def multilook(arr: da.Array, nlooks: IntOrInts) -> da.Array:
    """
    Multilook an array by simple averaging.

    Performs spatial averaging and decimation. Each element in the output array is the
    arithmetic mean of neighboring cells in the input array.

    Parameters
    ----------
    arr : dask.array.Array
        Input array.
    nlooks : int or iterable of int
        Number of looks along each axis of the input array.

    Returns
    -------
    out : dask.array.Array
        Multilooked array.

    Notes
    -----
    If the length of the input array along a given axis is not evenly divisible by the
    specified number of looks, any remainder samples from the end of the array will be
    discarded in the output.
    """
    # Normalize `nlooks` into a tuple with length equal to `arr.ndim`. If `nlooks` was a
    # scalar, take the same number of looks along each axis in the array.
    try:
        n = int(nlooks)  # type: ignore
        nlooks = (n,) * arr.ndim
    except TypeError:
        nlooks = tuple([int(n) for n in nlooks])  # type: ignore
        if len(nlooks) != arr.ndim:
            raise ValueError(
                f"length mismatch: length of nlooks ({len(nlooks)}) must match input"
                f" array rank ({arr.ndim})"
            )

    # Convince static type checkers that `nlooks` is a tuple of ints now.
    nlooks = cast(Tuple[int, ...], nlooks)

    # The number of looks must be at least 1 and at most the size of the input array
    # along the corresponding axis.
    for m, n in zip(arr.shape, nlooks):
        if n < 1:
            raise ValueError("number of looks must be >= 1")
        elif n > m:
            raise ValueError("number of looks should not exceed array shape")

    # Warn if the number of looks along any axis is even-valued.
    if any(map(util.iseven, nlooks)):
        warnings.warn(
            (
                "one or more components of nlooks is even-valued -- this will result in"
                " a phase delay in the multilooked data equivalent to a half-bin shift"
            ),
            RuntimeWarning,
        )

    # Warn if any array dimensions are not integer multiples of `nlooks`.
    if any(m % n != 0 for (m, n) in zip(arr.shape, nlooks)):
        warnings.warn(
            (
                "input array shape is not an integer multiple of nlooks -- remainder"
                " samples will be excluded from output"
            ),
            RuntimeWarning,
        )

    axes = range(arr.ndim)
    nlooks_dict = {axis: n for (axis, n) in zip(axes, nlooks)}
    return _squeeze_chunks(da.coarsen(np.mean, arr, nlooks_dict, trim_excess=True))


def _squeeze_chunks(data: da.Array):
    """Remove size 0 chunks from a dask.Array's explicit chunks."""
    nonzero_chunks = tuple(tuple(dim for dim in dims if dim > 0) for dims in data.chunks)
    return data.rechunk(nonzero_chunks)