import numpy as np
 
"""
Module to compute the IceCube point source likelihood
using publicly available information.

Based on the method described in:
Braun, J. et al., 2008. Methods for point source analysis 
in high energy neutrino telescopes. Astroparticle Physics, 
29(4), pp.299–305.

Currently well-defined for searches with
Northern sky muon neutrinos.
"""


class PointSourceLikelihood():
    """
    Calculate the point source likelihood for a given 
    neutrino dataset - in terms of reconstructed 
    energies and arrival directions.
    """    
    
    def __init__(self, direction_likelihood, energy_likelihood, event_coords, energies, source_coord):
        """
        Calculate the point source likelihood for a given 
        neutrino dataset - in terms of reconstructed 
        energies and arrival directions.
        
        :param direction_likelihood: An instance of SpatialGaussianLikelihood.
        :param energy_likelihood: An instance of MarginalisedEnergyLikelihood.
        :param event_coords: List of (ra, dec) tuples for reconstructed coords.
        :param energies: The reconstructed nu energies.
        :param source_coord: (ra, dec) pf the point to test.
        """

        self._direction_likelihood = direction_likelihood 

        self._energy_likelihood = energy_likelihood

        self._band_width = 5 * self._direction_likelihood._sigma # degrees

        self._event_coords = event_coords
        
        self._energies = energies

        self._source_coord = source_coord

        self.N = len(energies)

        self._bg_index = 3.7
        
        
    def _signal_likelihood(self, event_coord, source_coord, energy, index):

        return direction_likelihood(event_coord, source_coord) * energy_likelihood(energy, index)


    def _background_likelihood(self, energy):

        return energy_likelihood(energy, self._bg_index) / np.deg2rad(self._band_width)
    
        
    def __call__(self, ns, index):
        """
        Evaluate the PointSourceLikelihood for the given
        neutrino dataset.

        :param ns: Number of source counts.
        :param index: Spectral index of the source.
        """

        log_likelihood = 0

        for i in range(N):
            
            signal = (ns / self.N) * self._signal_likelihood(self._event_coords[i], self._source_coord, self._energies[i], index)

            bg = (1 - (ns / self.N)) * self._background_likelihood(self._energies[i])

            log_likelihood += np.log(signal + bg)

        return log_likelihood
        
                
class MarginalisedEnergyLikelihood():
    """
    Compute the marginalised energy likelihood by using a 
    simulation of a large number of reconstructed muon 
    neutrino tracks. 
    """
    
    
    def __init__(self, energy, sim_index=1.5):
        """
        Compute the marginalised energy likelihood by using a 
        simulation of a large number of reconstructed muon 
        neutrino tracks. 
        
        :param energy: Reconstructed muon energies (preferably many).
        :param sim_index: Spectral index of source spectrum in sim.
        """

        self._energy = energy

        self._sim_index = sim_index

        
    def _calc_weights(self, new_index):

        return  np.power(self._energy, self._sim_index - self._new_index)


    def __call__(self, E, new_index, min_E=1e2, max_E=1e9):
        """
        P(Ereco | index) = \int dEtrue P(Ereco | Etrue) P(Etrue | index)
        """

        self._new_index = new_index

        self._weights = self._calc_weights(new_index)

        bins = np.linspace(np.log10(min_E), np.log10(max_E)) # GeV
        
        self._hist, _ = np.histogram(np.log10(self._energy), bins=bins, weights=self._weights, density=True)
        
        E_index = np.digitize(np.log10(E), bins) - 1

        return self._hist[E_index]
        


class SpatialGaussianLikelihood():
    """
    Spatial part of the point source likelihood.

    P(x_i | x_s) where x is the direction (unit_vector).
    """
    

    def __init__(self, angular_resolution):
        """
        Spatial part of the point source likelihood.
        
        P(x_i | x_s) where x is the direction (unit_vector).
        
        :param angular_resolution; Angular resolution of detector [deg]. 
        """

        # @TODO: Init with some sigma as a function of E?
        
        self._sigma = angular_resolution

    
    def __call__(self, event_coord, source_coord):
        """
        Use the neutrino energy to determine sigma and 
        evaluate the likelihood.

        P(x_i | x_s) = (1 / (2pi * sigma^2)) * exp( |x_i - x_s|^2/ (2*sigma^2) )

        :param event_coord: (ra, dec) of event [rad].
        :param source_coord: (ra, dec) of point source [rad].
        """

        sigma_rad = np.deg2rad(self._sigma)

        ra, dec = event_coord
                
        src_ra, src_dec = source_coord
        
        norm = 0.5 / (np.pi * sigma_rad**2)

        # Calculate the cosine of the distance of the source and the event on
        # the sphere.
        cos_r = np.cos(src_ra - ra) * np.cos(src_dec) * np.cos(dec) + np.sin(src_dec) * np.sin(dec)
        
        # Handle possible floating precision errors.
        if cos_r < -1.0:
            cos_r = 1.0
        if cos_r > 1.0:
            cos_r = 1.0

        r = np.arccos(cos_r)
         
        dist = np.exp( -0.5*(r / sigma_rad)**2 )

        return norm * dist
