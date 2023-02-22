#!/usr/bin/env python
# encoding: utf-8
"""
Provides colors for clustering routines.
"""

import numpy as np

cmap = [[0, 0, 0.5625], [0, 0, 0.6250], [0, 0, 0.6875], [0, 0, 0.7500],
        [0, 0, 0.8125], [0, 0, 0.8750], [0, 0, 0.9375], [0, 0, 1],
        [0, 0.0625, 1], [0, 0.1250, 1], [0, 0.1875, 1], [0, 0.2500, 1],
        [0, 0.3125, 1], [0, 0.3750, 1], [0, 0.4375, 1], [0, 0.5, 1],
        [0, 0.5625, 1], [0, 0.6250, 1], [0, 0.6875, 1], [0, 0.75, 1],
        [0, 0.8125, 1], [0, 0.8750, 1], [0, 0.9375, 1], [0, 1, 1],
        [0.0625, 1, 0.9375], [0.1250, 1, 0.8750], [0.1875, 1, 0.8125],
        [0.2500, 1, 0.7500], [0.3125, 1, 0.6875], [0.3750, 1, 0.6250],
        [.4375, 1, 0.5625], [0.5000, 1, 0.5000], [0.5625, 1, 0.4375],
        [0.6250, 1, 0.3750], [0.6875, 1, 0.3125], [0.7500, 1, 0.2500],
        [0.8125, 1, 0.1875], [0.8750, 1, 0.1250], [0.9375, 1, 0.0625],
        [1, 1, 0], [1, 0.9375, 0], [1, 0.8750, 0], [1, 0.8125, 0],
        [1, 0.7500, 0], [1, 0.6875, 0], [1, 0.6250, 0], [1, 0.5625, 0],
        [1, 0.5000, 0], [1, 0.4375, 0], [1, 0.3750, 0], [1, 0.3125, 0],
        [1, 0.2500, 0], [1, 0.1875, 0], [1, 0.1250, 0], [1, 0.0625, 0],
        [1, 0, 0], [0.9375, 0, 0], [0.8750, 0, 0], [0.8125, 0, 0],
        [0.7500, 0, 0], [0.6875, 0, 0], [0.6250, 0, 0], [0.5625, 0, 0],
        [0.5000, 0, 0]]


def CZ_Clust_2_color(dt):
    """
    TODO: Add doc-string.

    :param dt:
    :type dt: float

    :returns: List of 3 values between 0 and 1 for color indexing.

    """

    tt = list(range(0, 105, 5))
    liste = [dt-tt[i] for i in range(len(tt))]
    ind1 = np.where(np.abs(liste) == np.min(np.abs(liste)))[0]
    ind2 = ind1[0]
    ind = int(np.max(round(len(cmap)*ind2/len(tt))))
    color = cmap[ind]

    return color


def CZ_W_2_color(dt):
    """
    TODO: Add doc-string.

    :param dt:
    :type dt: float

    :returns: List of 3 values between 0 and 1 for color indexing.

    """

    tt = list(range(1, 21, 1))
    liste = [dt-tt[i] for i in range(len(tt))]
    ind1 = np.where(np.abs(liste) == np.min(np.abs(liste)))[0]
    ind2 = ind1[0]
    ind = int(np.max(round(len(cmap)*ind2/len(tt))))
    color = cmap[ind]

    return color
