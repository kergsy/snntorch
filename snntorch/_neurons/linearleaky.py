import torch
from torch import nn
from torch.nn import functional as F
from profilehooks import profile

# from .neurons import LIF
from .stateleaky import StateLeaky

class LinearLeaky(StateLeaky):
    """
    TODO: write some docstring similar to SNN.Leaky

     Jason wrote:
-      beta = (1 - delta_t / tau), can probably set delta_t to "1"
-      if tau > delta_t, then beta: (0, 1)
    """

    def __init__(
        self,
        beta,
        in_features, 
        out_features,
        bias=True, 
        device=None, 
        dtype=None,
        threshold=1.0,
        spike_grad=None,
        surrogate_disable=False,
        learn_beta=False,
        learn_threshold=False,
        state_quant=False, 
        output=True,
        graded_spikes_factor=1.0, 
        learn_graded_spikes_factor=False,
    ):
        super().__init__(
            beta=beta,
            threshold=threshold,
            spike_grad=spike_grad,
            surrogate_disable=surrogate_disable,
            learn_beta=learn_beta,
            learn_threshold=learn_threshold,
            state_quant=state_quant,
            output=output,
            graded_spikes_factor=graded_spikes_factor,
            learn_graded_spikes_factor=learn_graded_spikes_factor,
        )

        self._tau_buffer(self.beta, learn_beta)
        self.linear = nn.Linear(in_features=in_features, out_features=out_features,
                                device=device, dtype=dtype, bias=bias)
        self.linear = nn.Linear(in_features=in_features, out_features=out_features,
                                device=device, dtype=dtype, bias=bias)

    @property
    def beta(self): 
        return (self.tau-1) / self.tau

    # @profile(skip=True, stdout=True, filename='baseline.prof')
    def forward(self, input_):

        input_ = self.linear(input_.reshape(-1, self.linear.in_features))  # TODO: input_ must be transformed T x B x C --> (T*B) x C
        self.mem = self._base_state_function(input_)

        if self.state_quant:
            self.mem = self.state_quant(self.mem)

        if self.output:
            self.spk = self.fire(self.mem) * self.graded_spikes_factor
            return self.spk, self.mem

        else:
            return self.mem

    def _base_state_function(self, input_):
        # init time steps arr
        num_steps, batch, channels = input_.shape
        time_steps = torch.arange(0, num_steps, device=input_.device)
        assert time_steps.shape == (num_steps,)
        time_steps = time_steps.unsqueeze(1).expand(num_steps, channels)

        # init decay filter
        decay_filter = torch.exp(-time_steps / self.tau).to(input_.device)
        assert decay_filter.shape == (num_steps, channels)

        # prepare for convolution
        input_ = input_.permute(1, 2, 0)
        assert input_.shape == (batch, channels, num_steps)
        decay_filter = decay_filter.permute(1, 0).unsqueeze(1)
        assert decay_filter.shape == (channels, 1, num_steps)

        conv_result = full_mode_conv1d_truncated(input_, decay_filter)
        assert conv_result.shape == (batch, channels, num_steps)

        return conv_result.permute(2, 0, 1)  # return membrane potential trace
    
    def _tau_buffer(self, beta, learn_beta):
        if not isinstance(beta, torch.Tensor):
            beta = torch.as_tensor(beta)
        
        tau = 1 / (1 - beta)

        if learn_beta:
            self.tau = nn.Parameter(tau)
        else:
            self.register_buffer("tau", tau)

# TODO: throw exceptions if calling subclass methods we don't want to use
# fire_inhibition
# mem_reset, init, detach, zeros, reset_mem, init_leaky
# detach_hidden, reset_hidden

