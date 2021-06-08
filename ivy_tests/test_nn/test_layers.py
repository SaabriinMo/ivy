"""
Collection of tests for templated neural network layers
"""

# global
import pytest
import numpy as np

# local
import ivy
import ivy_tests.helpers as helpers
from ivy.core.container import Container


# Linear #
# -------#

@pytest.mark.parametrize(
    "bs_ic_oc_target", [
        ([1, 2], 4, 5, [[0.30230279, 0.65123089, 0.30132881, -0.90954636, 1.08810135]]),
    ])
@pytest.mark.parametrize(
    "with_v", [True, False])
@pytest.mark.parametrize(
    "dtype_str", ['float32'])
@pytest.mark.parametrize(
    "tensor_fn", [ivy.array, helpers.var_fn])
def test_linear_layer(bs_ic_oc_target, with_v, dtype_str, tensor_fn, dev_str, call):
    # smoke test
    batch_shape, input_channels, output_channels, target = bs_ic_oc_target
    x = ivy.cast(ivy.linspace(ivy.zeros(batch_shape), ivy.ones(batch_shape), input_channels), 'float32')
    if with_v:
        np.random.seed(0)
        wlim = (6 / (output_channels + input_channels)) ** 0.5
        w = ivy.variable(ivy.array(np.random.uniform(-wlim, wlim, (output_channels, input_channels)), 'float32'))
        b = ivy.variable(ivy.zeros([output_channels]))
        v = Container({'w': w, 'b': b})
    else:
        v = None
    linear_layer = ivy.Linear(input_channels, output_channels, v=v)
    ret = linear_layer(x)
    # type test
    assert ivy.is_array(ret)
    # cardinality test
    assert ret.shape == tuple(batch_shape + [output_channels])
    # value test
    if not with_v:
        return
    assert np.allclose(call(linear_layer, x), np.array(target))
    # compilation test
    if call is helpers.torch_call:
        # pytest scripting does not **kwargs
        return
    helpers.assert_compilable(linear_layer)


# Convolutions #
# -------------#

@pytest.mark.parametrize(
    "x_n_fs_n_pad_n_res", [
        ([[[0.], [3.], [0.]]],
         3,
         "SAME",
         [[[1.0679483],
           [2.2363136],
           [0.5072848]]]),

        ([[[0.], [3.], [0.]] for _ in range(5)],
         3,
         "SAME",
         [[[1.0679483], [2.2363136], [0.5072848]] for _ in range(5)]),

        ([[[0.], [3.], [0.]]],
         3,
         "VALID",
         [[[2.2363136]]])])
@pytest.mark.parametrize(
    "with_v", [True, False])
@pytest.mark.parametrize(
    "dtype_str", ['float32'])
@pytest.mark.parametrize(
    "tensor_fn", [ivy.array, helpers.var_fn])
def test_conv1d_layer_training(x_n_fs_n_pad_n_res, with_v, dtype_str, tensor_fn, dev_str, call):
    if call in [helpers.tf_call, helpers.tf_graph_call] and 'cpu' in dev_str:
        # tf conv1d does not work when CUDA is installed, but array is on CPU
        pytest.skip()
    if call in [helpers.np_call, helpers.jnp_call]:
        # numpy and jax do not yet support conv1d
        pytest.skip()
    # smoke test
    x, filter_size, padding, target = x_n_fs_n_pad_n_res
    x = tensor_fn(x, dtype_str, dev_str)
    target = np.asarray(target)
    input_channels = x.shape[-1]
    output_channels = target.shape[-1]
    batch_size = x.shape[0]
    width = x.shape[1]
    if with_v:
        np.random.seed(0)
        wlim = (6 / (output_channels + input_channels)) ** 0.5
        w = ivy.variable(ivy.array(np.random.uniform(
            -wlim, wlim, (filter_size, output_channels, input_channels)), 'float32'))
        b = ivy.variable(ivy.zeros([1, 1, output_channels]))
        v = Container({'w': w, 'b': b})
    else:
        v = None
    conv1d_layer = ivy.Conv1D(input_channels, output_channels, filter_size, 1, padding, v=v)
    ret = conv1d_layer(x)
    # type test
    assert ivy.is_array(ret)
    # cardinality test
    new_width = width if padding == 'SAME' else width - filter_size + 1
    assert ret.shape == (batch_size, new_width, output_channels)
    # value test
    if not with_v:
        return
    assert np.allclose(call(conv1d_layer, x), target)
    # compilation test
    if call is helpers.torch_call:
        # pytest scripting does not **kwargs
        return
    helpers.assert_compilable(conv1d_layer)


# LSTM #
# -----#

@pytest.mark.parametrize(
    "b_t_ic_hc_otf_sctv", [
        (2, 3, 4, 5, [0.93137765, 0.9587628, 0.96644664, 0.93137765, 0.9587628, 0.96644664], 3.708991),
    ])
@pytest.mark.parametrize(
    "with_v", [True, False])
@pytest.mark.parametrize(
    "with_initial_state", [True, False])
@pytest.mark.parametrize(
    "dtype_str", ['float32'])
@pytest.mark.parametrize(
    "tensor_fn", [ivy.array, helpers.var_fn])
def test_lstm_layer(b_t_ic_hc_otf_sctv, with_v, with_initial_state, dtype_str, tensor_fn, dev_str, call):
    # smoke test
    b, t, input_channels, hidden_channels, output_true_flat, state_c_true_val = b_t_ic_hc_otf_sctv
    x = ivy.cast(ivy.linspace(ivy.zeros([b, t]), ivy.ones([b, t]), input_channels), 'float32')
    if with_initial_state:
        init_h = ivy.ones([b, hidden_channels])
        init_c = ivy.ones([b, hidden_channels])
        initial_state = ([init_h], [init_c])
    else:
        initial_state = None
    if with_v:
        kernel = ivy.variable(ivy.ones([input_channels, 4*hidden_channels])*0.5)
        recurrent_kernel = ivy.variable(ivy.ones([hidden_channels, 4*hidden_channels])*0.5)
        v = Container({'input': {'layer_0': {'w': kernel}},
                       'recurrent': {'layer_0': {'w': recurrent_kernel}}})
    else:
        v = None
    lstm_layer = ivy.LSTM(input_channels, hidden_channels, v=v)
    output, (state_h, state_c) = lstm_layer(x, initial_state=initial_state)
    # type test
    assert ivy.is_array(output)
    assert ivy.is_array(state_h[0])
    assert ivy.is_array(state_c[0])
    # cardinality test
    assert output.shape == (b, t, hidden_channels)
    assert state_h[0].shape == (b, hidden_channels)
    assert state_c[0].shape == (b, hidden_channels)
    # value test
    if not with_v or not with_initial_state:
        return
    output_true = np.tile(np.asarray(output_true_flat).reshape((b, t, 1)), (1, 1, hidden_channels))
    state_c_true = np.ones([b, hidden_channels]) * state_c_true_val
    output, (state_h, state_c) = call(lstm_layer, x, initial_state=initial_state)
    assert np.allclose(output, output_true, atol=1e-6)
    assert np.allclose(state_c, state_c_true, atol=1e-6)
    # compilation test
    if call in [helpers.torch_call]:
        # this is not a backend implemented function
        pytest.skip()
    helpers.assert_compilable(ivy.lstm_update)
