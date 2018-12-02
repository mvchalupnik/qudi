from core.module import Base, ConfigOption
from interface.rng_interface import RNGInterface

import random


class RNG(Base, RNGInterface):

    """Random Number Generator quasi-instrument.
    Every time get_random_value() method is called, it takes self.mean and self.noise
    and returns the following random number (a list of samples_number random numbers):
        mean + noise*( random.random()-0.5 )
    """
    _modclass = 'RNG'
    _modtype = 'hardware'

    # config
    _mean = ConfigOption(name='mean', default=0.0, missing='warn')
    _noise = ConfigOption(name='noise', default=0.0, missing='warn')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """
        pass
        # self.mean = self._mean
        # self.noise = self._noise

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        pass
        # self.log.warning('rng>deactivation')

    def set_params(self, mean=None, noise=None):
        """ Set mean value and noise amplitude of the RNG

        @param float mean: optional, mean value of the RNG
        @param float noise: optional, noise amplitude of the RNG, max deviation of random number from mean
        @return int: error code (0:OK, -1:error)
        """
        if mean is not None:
            self._mean = mean
        if noise is not None:
            self._noise = noise

    def get_params(self):
        """
        Get mean value and noise amplitude of the random number generator

        @return dict: {'mean': mean_value, 'noise': noise_amplitude}
        """
        return {'mean': self._mean, 'noise': self._noise}

    def get_random_value(self, samples_number=1):
        """
        Get the output value of the random number generator

        :param int samples_number: optional, number of random numbers to return
        :return list random_numbers: list of n_samples output random numbers
        """
        output = []

        for i in range(samples_number):
            random_value = self._mean + self._noise*(2*random.random() - 1)
            output.append(random_value)

        return output
