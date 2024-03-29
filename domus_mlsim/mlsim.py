"""

mlsim


Author
------
J. Brusey

Date
----
4-March-2021


MLSim class that packages up a machine learnt model and scaler.

"""

import numpy as np

from .partial_scaler import PartialScaler


class MLSim:
    """Discrete time simulator derived from machine-learnt model.

    The idea of this class is to wrap up the ML simulator and deal
    with scaling, lagged state and actions, and differing intervals to
    make the simulator easier to call. The initial state and prior
    actions are provided to the constructor and then the simulator can
    be run by successive calls to ~step~.

    """

    def __init__(
        self,
        scaler_and_model,
        initial_state,
        xlag,
        ulag,
        xlen,
        ulen,
        interval=1,
        initial_clock=0,
        prior_actions=None,
        ut_min=None,
        ut_max=None,
    ):
        """construct a simulator object

        Parameters
        ----------
        scaler_and_model : tuple

          tuple containing scaler and model. The scaler transforms the
          combined x, u vector, while model provides a single step
          simulator for scaled values.

        initial_state : array-like

          vector containing initial state. Can also be a 2D array of
          xlag vectors for more complete initialisation. If only a
          single vector is supplied, that vector is replicated xlag
          times to make up the initial state.

        xlag : integer

          number of lagged state values. This must match the
          parameters used to develop the model

        ulag : integer

          number of lagged control values. This must match the
          parameters used to develop the model

        xlen : integer

          length of the state vector

        ulen : integer

          length of the control vector

        interval : integer

          time interval that the simulator was developed using, in
          seconds

        initial_clock : integer

          initial clock value so that first step will have time
          initial_clock + interval

        prior_actions : array

          ulag - 1 actions

        ut_min : array

          action array minimum values (used for clipping)

        ut_max : array

          action array maximum values (used for clipping)

        """
        scaler, self.model = scaler_and_model
        self.xt = initial_state
        assert initial_state.shape == (xlag, xlen)
        self.xlag = xlag
        self.ulag = ulag
        self.xlen = xlen
        self.ulen = ulen
        self.interval = interval
        self.clock = initial_clock
        self.prior_actions = prior_actions
        self.first = True
        self.x_scaler = PartialScaler(scaler, 0, xlen, xlen + ulen)
        self.u_scaler = PartialScaler(scaler, xlen, xlen + ulen, xlen + ulen)
        self.xt = self.x_scaler.transform(self.xt)
        self.ut_min = ut_min
        self.ut_max = ut_max
        assert (ut_min is None) == (ut_max is None)

    def step(self, ut):
        """simulate a single time step

        Given the current state history given by ~xt~ and current
        control history ~ut~

        Parameters
        ----------

        ut : array-like

          control input for current time step

        Returns
        -------

        (time, state vector at end of time step)

        """
        ut = np.array(ut, dtype=np.float32).reshape(1, -1)
        if self.ut_min is not None and self.ut_max is not None:
            ut = np.clip(ut, self.ut_min, self.ut_max)
        ut = self.u_scaler.transform(ut)
        assert self.xt.shape[0] == self.xlag
        assert self.xt.shape[1] == self.xlen
        if self.first:
            # for first step, assume that the same control inputs were
            # used for all previous steps
            if self.prior_actions is not None:
                self.ut = np.vstack([self.u_scaler.transform(self.prior_actions), ut])
            else:
                self.ut = np.vstack([ut] * (self.ulag))
            self.first = False
        else:
            self.ut = np.append(self.ut[1:], ut, axis=0)
        assert self.ut.shape == (self.ulag, self.ulen)

        x = np.hstack((self.xt.reshape(1, -1), self.ut.reshape(1, -1)))
        new_xt = self.model.predict(x)
        self.xt = np.append(self.xt[1:], new_xt.reshape(1, -1), axis=0)
        self.clock += self.interval
        return (self.clock, self.x_scaler.inverse_transform(new_xt)[0])
