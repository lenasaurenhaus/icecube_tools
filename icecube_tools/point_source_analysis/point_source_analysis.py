from ..point_source_likelihood.point_source_likelihood import (
    PointSourceLikelihood, TimeDependentPointSourceLikelihood
)
from ..point_source_likelihood.energy_likelihood import MarginalisedIntegratedEnergyLikelihood
from ..utils.data import data_directory, available_periods, ddict, Events
from ..utils.coordinate_transforms import *

import yaml

import healpy as hp
import numpy as np

from abc import ABC, abstractmethod

from os.path import join
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


"""
Classes to perform reproducible point source analyses
"""

class PointSourceAnalysis(ABC):
    """Meta class"""

    def __init__(self):
        pass


    @abstractmethod
    def load_config(self):
        pass


    @abstractmethod
    def write_config(self):
        pass


    @abstractmethod
    def apply_cuts(self):
        """Make cuts on loaded data"""
        pass



class MapScan(PointSourceAnalysis):

    #Config structure for yaml files
    config_structure = {
        "sources":
            {"nside": int, "npix": int, "ras": list, "decs": list}, 
        "data": {
            "periods": list,
            "cuts": {"northern": {"emin": float}, "equator": {"emin": float}, "southern": {"emin": float}
            }
        },
    }


    def __init__(self, path, events: Events):
        """
        Instantiate analysis object.
        :param path: Path to config
        :param events: object inheriting from :class:`icecube_tools.utils.data.Events`
        """

        self.events = events
        self.num_of_irf_periods = 0
        is_86 = False
        for p in events.periods:
            if "86" in p and not is_86:
                self.num_of_irf_periods += 1
                is_86 = True
            else:
                self.num_of_irf_periods += 1

       

        self.load_config(path)
        #self._make_output_arrays()
        
        


    def perform_scan(self):
        self._make_output_arrays()
        logger.info("Performing scan for periods: {}".format(self.events.periods))
        ra = self.events._ra
        dec = self.events._dec
        ang_err = self.events._ang_err
        reco_energy = self.events._reco_energy
        for c, (ra, dec) in enumerate(zip(self.ra_test, self.dec_test)):
            self._test_source((ra, dec), c, ra, dec, reco_energy, ang_err)


    def _test_source(self, source_coord, num, ra, dec, reco_energy, ang_err):
        if source_coord[1] <= np.deg2rad(10):
            likelihood = TimeDependentPointSourceLikelihood(
                source_coord,
                self.events.periods,
                ra,
                dec,
                reco_energy,
                ang_err,
                MarginalisedIntegratedEnergyLikelihood
            )
            if likelihood.N > 0:    # else somewhere division by zero
                self.ts[num] = likelihood.get_test_statistic()
                self.index[num] = likelihood._best_fit_index
                self.ns[num] = likelihood._best_fit_ns
                self.index_err[num] = likelihood.m.errors["index"]
                self.ns_err[num] = np.array(
                    [likelihood.m.errors[n] for n in likelihood.m.parameters if n != "index"]
                )


    def load_config(self, path):
        """
        Load analysis config from file
        """

        with open(path, "r") as f:
            config = yaml.load(f, Loader=yaml.Loader)
        logger.debug("{}".format(str(config)))    # ?!
        self.config = config
        source_config = config.get("sources")
        self.nside = source_config.get("nside")
        self.npix = source_config.get("npix")
        data_config = config.get("data")
        self.periods = data_config.get("periods")
        self.northern_emin = data_config.get("cuts").get("northern").get("emin")
        self.equator_emin = data_config.get("cuts").get("equator").get("emin")
        self.southern_emin = data_config.get("cuts").get("southern").get("emin")


    def write_config(self, path):
        """
        Write config used in analysis to file
        """

        config = ddict()
        try:
            config.add(self.nside, "sources", "nside")
        except AttributeError:
            pass
        try:
            config.add(self.npix, "sources", "npix")
        except AttributeError:
            pass

        config.add(self.periods, "data", "periods")
        config.add(self.northern_emin, "data", "cuts", "northern", "emin")
        config.add(self.equator_emin, "data", "cuts", "equator", "emin")
        config.add(self.southern_emin, "data", "cuts", "southern", "emin")

        with open(path, "w") as f:
            yaml.dump(config, f)


    def generate_sources(self, nside=True):
        """
        Generate sources from config-specified specifics
        """

        reload = True
        if self.nside is not None and nside:
            self.npix = hp.nside2npix(self.nside)
            logger.warning("Overwriting npix with nside = {}".format(self.nside))
        elif self.npix is not None and not nside:
            logger.info("Using npix = {}".format(self.npix))
        elif self.ra_test is not None and self.dec_test is not None:
            logger.info("Using provided ra and dec")
            reload = False

        if reload:
            logger.info(f"resolution in degrees: {hp.nside2resol(self.nside, arcmin=True)/60}")
            theta_test, phi_test = hp.pix2ang(self.nside, np.arange(self.npix), nest=False)
            ra_test, dec_test = spherical_to_icrs(theta_test, phi_test)
            self.ra_test = ra_test
            self.dec_test = dec_test

    
    def _make_output_arrays(self):
        if self.npix is not None:
            self.ts = np.zeros(self.npix)
            self.index = np.zeros(self.npix)
            self.ns = np.zeros((self.npix, self.num_of_irf_periods))
            self.ns_err = np.zeros((self.npix, self.num_of_irf_periods))
            self.index_err = np.zeros(self.npix)
        else:
            logger.error("Call generate_sources() first.")


    def apply_cuts(self):
        #make cuts based on config
        #incudes right now: energy only
        mask = []
        for p in self.periods:
            events = self.events.period(p)
            mask += np.nonzero(
                (events["reco_energy"] > self.northern_emin) & (events["dec"] > np.deg2rad(10)) &
                (events["reco_energy"] > self.equator_emin) & (events["dec"] < np.deg2rad(10) & 
                    events["reco_energy"] > self.equator_emin) & (events["dec"] > np.deg2rad(-10)) &
                (events["reco_energy"] > self.southern_emin) & (events["dec"] < np.deg2rad(10))
            )
        