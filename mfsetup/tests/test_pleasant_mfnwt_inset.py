"""
Tests for Pleasant Lake inset case
* MODFLOW-NWT
* SFR + Lake package
* Lake precip and evap specified with PRISM data; evap computed using evaporation.hamon_evaporation
* transient parent model with initial steady-state; copy unspecified data from parent
"""
import os
import numpy as np
import pandas as pd
import flopy
fm = flopy.modflow
from mfsetup import MFnwtModel
from mfsetup.discretization import find_remove_isolated_cells
from mfsetup.fileio import load_array
from .test_lakes import get_prism_data


def test_perioddata(get_pleasant_nwt):
    m = get_pleasant_nwt
    m._set_perioddata()
    assert m.perioddata['start_datetime'][0] == pd.Timestamp(m.cfg['dis']['start_date_time'])


def test_ibound(pleasant_nwt_with_dis):
    m = pleasant_nwt_with_dis
    # use pleasant lake extent as ibound
    is_pleasant_lake = m.lakarr[0]
    # clear out lake info, just for this test function
    m.cfg['model']['packages'].remove('lak')
    del m.cfg['lak']['source_data']
    # specify path relative to cfg file
    m.cfg['bas6']['source_data']['ibound'] = {'filename': 'pleasant/source_data/shps/all_lakes.shp'}
    m._reset_bc_arrays()
    bas6 = m.setup_bas6()
    bas6.write_file()
    assert np.array_equal(m.ibound, m.bas6.ibound.array)
    # find_remove_isolated_cells is run on ibound array but not in Lake setup
    assert np.array_equal(m.ibound[0], find_remove_isolated_cells(is_pleasant_lake))
    ibound = load_array(m.cfg['bas6']['ibound'])
    assert np.array_equal(m.ibound, ibound)


def test_setup_lak(pleasant_nwt_with_dis_bas6):
    m = pleasant_nwt_with_dis_bas6
    lak = m.setup_lak()
    lak.write_file()
    lak = fm.ModflowLak.load(lak.fn_path, m)
    datafile = '../../data/pleasant/source_data/PRISM_ppt_tmean_stable_4km_189501_201901_43.9850_-89.5522.csv'
    prism = get_prism_data(datafile)
    precip = [lak.flux_data[per][0][0] for per in range(1, m.nper)]
    assert np.allclose(lak.flux_data[0][0][0], prism['ppt_md'].mean())
    assert np.allclose(precip, prism['ppt_md'])


def test_ghb_setup(get_pleasant_nwt_with_dis_bas6):
    m = get_pleasant_nwt_with_dis_bas6
    ghb = m.setup_ghb()
    ghb.write_file()
    assert os.path.exists(ghb.fn_path)
    assert isinstance(ghb, fm.ModflowGhb)
    assert ghb.stress_period_data is not None

    # check for inactive cells
    spd0 = ghb.stress_period_data[0]
    k, i, j = spd0['k'], spd0['i'], spd0['j']
    inactive_cells = m.ibound[k, i, j] < 1
    assert not np.any(inactive_cells)

    # check that heads are above layer botms
    assert np.all(spd0['bhead'] > m.dis.botm.array[k, i, j])
    assert np.all(spd0['cond'] == m.cfg['ghb']['cond'])


def test_wel_setup(get_pleasant_nwt_with_dis_bas6):

    m = get_pleasant_nwt_with_dis_bas6
    m.setup_upw()

    # test without tmr
    m.cfg['model']['perimeter_boundary_type'] = 'specified head'
    wel = m.setup_wel()
    wel.write_file()
    assert os.path.exists(m.cfg['wel']['output_files']['lookup_file'])
    df = pd.read_csv(m.cfg['wel']['output_files']['lookup_file'])
    bfluxes0 = df.loc[(df.comments == 'boundary_flux') & (df.per == 0)]
    assert len(bfluxes0) == 0
    # verify that water use fluxes are negative
    assert wel.stress_period_data[0]['flux'].max() <= 0.
    # verify that water use fluxes are in sp after 0
    # assuming that no wells shut off
    nwells0 = len(wel.stress_period_data[0][wel.stress_period_data[0]['flux'] != 0])
    n_added_wels = len(m.cfg['wel']['wells'])
    for k, spd in wel.stress_period_data.data.items():
        if k == 0:
            continue
        assert len(spd) >= nwells0 + n_added_wels


def test_model_setup(full_pleasant_nwt):
    m = full_pleasant_nwt
    assert isinstance(m, MFnwtModel)


def test_model_setup_and_run(pleasant_nwt_model_run):
    m = pleasant_nwt_model_run