import numpy as np
import pytest
from ..discretization import (fix_model_layer_conflicts, verify_minimum_layer_thickness,
                              fill_layers, make_idomain, get_layer_thicknesses,
                              deactivate_idomain_above)


pytest.fixture(scope="function")
def idomain(botm):
    nlay, nrow, ncol = botm.shape
    nr = int(np.floor(nrow*.35))
    nc = int(np.floor(ncol*.35))
    idomain = np.zeros((nlay, nrow, ncol), dtype=int)
    idomain[:, nr:-nr, nc:-nc] = 1
    idomain[-1, :, :] = 1
    return idomain.astype(int)


def test_conflicts():
    nlay, nrow, ncol = 13, 100, 100
    minimum_thickness = 1.0
    top = np.ones((nrow, ncol), dtype=float) * nlay
    botm = np.ones((nlay, nrow, ncol)) * np.reshape(np.arange(nlay)[::-1], (nlay, 1, 1))

    def idomain(botm):
        nlay, nrow, ncol = botm.shape
        nr = int(np.floor(nrow * .35))
        nc = int(np.floor(ncol * .35))
        idomain = np.zeros((nlay, nrow, ncol), dtype=int)
        idomain[:, nr:-nr, nc:-nc] = 1
        idomain[-1, :, :] = 1
        return idomain.astype(int)
    idomain = idomain(botm)

    isvalid = verify_minimum_layer_thickness(top, botm, idomain, minimum_thickness)
    assert isvalid
    botm[0, 0, 0] = -1
    isvalid = verify_minimum_layer_thickness(top, botm, idomain, minimum_thickness)
    assert isvalid
    i, j = int(nrow/2), int(ncol/2)
    botm[0, i, j] = -1
    isvalid = verify_minimum_layer_thickness(top, botm, idomain, minimum_thickness)
    assert not isvalid
    botm2 = fix_model_layer_conflicts(top, botm, idomain, minimum_thickness)
    isvalid = verify_minimum_layer_thickness(top, botm2, idomain, minimum_thickness)
    assert isvalid


@pytest.fixture
def all_layers():
    """Sample layer elevation grid where some layers
    are completely pinched out (no botm elevation specified) and
    others partially pinched out (botms specified locally).

    Returns
    -------

    """
    nlay, nrow, ncol = 9, 10, 10
    all_layers = np.zeros((nlay + 1, nrow, ncol), dtype=float) * np.nan
    ni = 6
    nj = 3
    all_layers[0, 2:2 + ni, 2:2 + ni] = 10  # locally specified botms
    # layer 1 is completely pinched out
    all_layers[2] = 8  # global botm elevation of 8
    all_layers[5, 2:2 + ni, 2:2 + nj] = 5  # locally specified botms
    all_layers[9] = 1
    return all_layers


def test_fill_layers(all_layers):
    nlay, nrow, ncol = all_layers.shape
    ni = len(set(np.where(~np.isnan(all_layers[0]))[0]))
    nj = len(set(np.where(~np.isnan(all_layers[5]))[1]))
    filled = fill_layers(all_layers)
    a = np.array([ni*ni, ni*ni, nrow*ncol,
                  ni*nj, ni*nj, ni*nj, ni*nj, ni*nj, ni*nj,
                  nrow*ncol])
    b = np.arange(1, 11, dtype=float)[::-1]
    assert np.array_equal(np.nansum(filled, axis=(1, 2)),
                          a*b)
    make_plot = False
    if make_plot:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        for i in range(nlay):
            lw = 0.5
            if i in [0, 2, 5, 9]:
                lw = 2
            ax.plot(all_layers[i, 5, :], lw=lw)


def test_make_idomain(all_layers):
    top = all_layers[0].copy()
    botm = all_layers[1:].copy()
    nodata = -9999
    botm[-1, 0, 0] = nodata
    botm[-2] = 2
    botm[-2, 2, 2] = np.nan
    idomain = make_idomain(top, botm, nodata=nodata,
                           minimum_layer_thickness=1,
                           drop_thin_cells=True,
                           tol=1e-4)
    # test idomain based on nans
    assert np.array_equal(idomain[:, 2, 2].astype(bool), ~np.isnan(botm[:, 2, 2]))
    # test idomain based on nodata
    assert idomain[-1, 0, 0] == 0
    # test idomain based on layer thickness
    assert idomain[-1].sum() == 1
    assert idomain[-2].sum() == 99
    # test that nans in the model top result in the highest active botms being excluded
    # (these cells have valid botms, but no tops)
    assert idomain[:, 0, 0].sum() == 1
    # in all_layers, cells with valid tops are idomain=0
    # because all botms in layer 1 are nans
    assert idomain[0].sum() == 0

    # test edge case of values that match the layer thickness when tol=0
    idomain = make_idomain(top, botm, nodata=nodata,
                           minimum_layer_thickness=1,
                           drop_thin_cells=True,
                           tol=0)
    assert idomain[-1].sum() == 99


def test_get_layer_thicknesses(all_layers):
    top = all_layers[0].copy()
    botm = all_layers[1:].copy()

    thicknesses = get_layer_thicknesses(top, botm)
    assert thicknesses[-1, 0, 0] == 7
    b = thicknesses[:, 0, 0]
    assert np.array_equal(b[~np.isnan(b)], np.array([7.]))
    expected = np.zeros(botm.shape[0]) * np.nan
    expected[1] = 2
    expected[4] = 3
    expected[-1] = 4
    assert np.allclose(thicknesses[:, 2, 2].copy(), expected, equal_nan=True)


def test_deactivate_idomain_above(all_layers):
    top = all_layers[0].copy()
    botm = all_layers[1:].copy()
    idomain = make_idomain(top, botm,
                           minimum_layer_thickness=1,
                           drop_thin_cells=True,
                           tol=1e-4)
    reach_data = {'k': [2, 8],
                  'i': [2, 3],
                  'j': [2, 3]}
    idomain2 = deactivate_idomain_above(idomain, reach_data)
    assert idomain2[:, 2, 2].sum() == idomain[:, 2, 2].sum() -1
    assert idomain2[:, 3, 3].sum() == 1
