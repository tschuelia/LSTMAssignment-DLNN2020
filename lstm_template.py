"""
Minimal character-level LSTM model. Written by Ngoc Quan Pham
Code structure borrowed from the Vanilla RNN model from Andreij Karparthy @karparthy.
BSD License
"""
import sys
from random import uniform

import numpy as np


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def dsigmoid(y):
    return y * (1 - y)


def dtanh(x):
    return 1 - x * x


# The numerically stable softmax implementation
def softmax(x):
    # assuming x shape is [feature_size, batch_size]
    e_x = np.exp(x - np.max(x, axis=0))
    return e_x / e_x.sum(axis=0)


# data I/O
data = open("data/input.txt", "r").read()  # should be simple plain text file
chars = sorted(list(set(data)))
data_size, vocab_size = len(data), len(chars)
print("data has %d characters, %d unique." % (data_size, vocab_size))
char_to_ix = {ch: i for i, ch in enumerate(chars)}
ix_to_char = {i: ch for i, ch in enumerate(chars)}
std = 0.1

option = sys.argv[1]

# hyperparameters
emb_size = 64
hidden_size = 128  # size of hidden layer of neurons
seq_length = 128  # number of steps to unroll the RNN for
learning_rate = 0.1
max_updates = 500000
batch_size = 8
epochs = 5000

concat_size = emb_size + hidden_size

# model parameters
# char embedding parameters
Wex = np.random.randn(emb_size, vocab_size) * std  # embedding layer

# LSTM parameters
Wf = np.random.randn(hidden_size, concat_size) * std  # forget gate
Wi = np.random.randn(hidden_size, concat_size) * std  # input gate
Wo = np.random.randn(hidden_size, concat_size) * std  # output gate
Wc = np.random.randn(hidden_size, concat_size) * std  # c term

bf = np.zeros((hidden_size, 1))  # forget bias
bi = np.zeros((hidden_size, 1))  # input bias
bo = np.zeros((hidden_size, 1))  # output bias
bc = np.zeros((hidden_size, 1))  # memory bias

# Output layer parameters
Why = np.random.randn(vocab_size, hidden_size) * std  # hidden to output
by = np.random.randn(vocab_size, 1) * std  # output bias

data_stream = np.asarray([char_to_ix[char] for char in data])
print(data_stream.shape)

bound = (data_stream.shape[0] // (seq_length * batch_size)) * (seq_length * batch_size)
cut_stream = data_stream[:bound]
cut_stream = np.reshape(cut_stream, (batch_size, -1))


def forward(inputs, targets, memory):
    """
    inputs,targets are both list of integers.
    hprev is Hx1 array of initial hidden state
    returns the loss, gradients on model parameters, and last hidden state
    """
    h_prev, c_prev = memory
    """
    xs = inputs
    wes = word embeddings
    hs = hidden states (a)
    ys = unnormalized outputs (no softmax applied)
    ps = predictions
    cs = memories
    zs = concatenated a[t-1] x[t]
    ins = input gates
    c_s = candidates for c
    ls = labels
    os = output gates
    fs = forget gates
    """
    xs, wes, hs, ys, ps, cs, zs, ins, c_s, ls = {}, {}, {}, {}, {}, {}, {}, {}, {}, {}
    os, fs = {}, {}
    hs[-1] = np.copy(h_prev)
    cs[-1] = np.copy(c_prev)

    loss = 0
    input_length = inputs.shape[0]

    # forward pass
    for t in range(input_length):
        xs[t] = np.zeros((vocab_size, batch_size))  # encode in 1-of-k representation
        for b in range(batch_size):
            xs[t][inputs[t][b]][b] = 1

        # convert word indices to word embeddings
        wes[t] = np.dot(Wex, xs[t])

        # LSTM cell operation
        # first concatenate the input and h to get z
        zs[t] = np.row_stack((hs[t - 1], wes[t]))

        # compute the forget gate
        # f = sigmoid(Wf * z + bf)
        fs[t] = sigmoid(np.dot(Wf, zs[t]) + bf)

        # compute the input gate
        ins[t] = sigmoid(np.dot(Wi, zs[t]) + bi)
        # i = sigmoid(Wi * z + bi)
        # compute the candidate memory
        # c_ = tanh(Wc * z + bc)
        c_s[t] = np.tanh(np.dot(Wc, zs[t]) + bc)

        # new memory: applying forget gate on the previous memory
        # and then adding the input gate on the candidate memory
        # c_t = f * c_(t-1) + i * c_
        cs[t] = fs[t] * cs[t - 1] + ins[t] * c_s[t]

        # output gate
        # o = sigmoid(Wo * z + bo)
        os[t] = sigmoid(np.dot(Wo, zs[t]) + bo)

        # new hidden state
        # h = output_gate * tanh(c_t)
        hs[t] = os[t] * np.tanh(cs[t])

        # DONE LSTM
        # output layer - softmax and cross-entropy loss
        # unnormalized log probabilities for next chars
        ys[t] = np.dot(Why, hs[t]) + by
        # softmax for probabilities for next chars
        ps[t] = softmax(ys[t])

        # label
        ls[t] = np.zeros((vocab_size, batch_size))
        for b in range(batch_size):
            ls[t][targets[t][b]][b] = 1

        # cross-entropy loss
        loss_t = np.sum(-np.log(ps[t]) * ls[t])
        loss += loss_t
        # loss += -np.log(ps[t][targets[t],0])

        # update h_prev and c_prev for next iteration
        h_prev = hs[t]
        c_prev = cs[t]

    activations = (xs, wes, hs, ys, ps, cs, zs, ins, c_s, ls, os, fs)
    memory = (hs[-1], cs[-1])

    return loss, activations, memory


def backward(activations, clipping=True):
    xs, wes, hs, ys, ps, cs, zs, ins, c_s, ls, os, fs = activations

    # backward pass: compute gradients going backwards
    # Here we allocate memory for the gradients
    dWex, dWhy = np.zeros_like(Wex), np.zeros_like(Why)
    dby = np.zeros_like(by)
    dWf, dWi, dWc, dWo = (
        np.zeros_like(Wf),
        np.zeros_like(Wi),
        np.zeros_like(Wc),
        np.zeros_like(Wo),
    )
    dbf, dbi, dbc, dbo = (
        np.zeros_like(bf),
        np.zeros_like(bi),
        np.zeros_like(bc),
        np.zeros_like(bo),
    )

    dh_next = np.zeros_like(hs[0])
    dc_next = np.zeros_like(cs[0])

    input_length = len(xs)

    # back propagation through time starts here
    for t in reversed(range(input_length)):
        # computing the gradients here
        dps = ps[t] - ls[t]
        dWhy += np.dot(dps, hs[t].T)
        dby += np.sum(dps, axis=-1, keepdims=True)

        # gradient of the hidden state
        dh = np.dot(Why.T, dps) + dh_next

        # gradient of the output gate
        do = np.tanh(cs[t]) * dh * dsigmoid(os[t])
        dWo += np.dot(do, zs[t].T)
        dbo += np.sum(do, axis=-1, keepdims=True)

        # gradient of the memory
        # for some reason applying the tanh to the c value is required
        # even though we think this is not actually correct?
        dc = os[t] * dh * dtanh(np.tanh(cs[t])) + dc_next

        # gradient of the update gate
        di = c_s[t] * dc * dsigmoid(ins[t])
        dWi += np.dot(di, zs[t].T)
        dbi += np.sum(di, axis=-1, keepdims=True)

        # gradient of the candidate gate
        dcand = ins[t] * dc * dtanh(c_s[t])
        dWc += np.dot(dcand, zs[t].T)
        dbc += np.sum(dcand, axis=-1, keepdims=True)

        # gradient of the forget gate
        df = cs[t - 1] * dc * dsigmoid(fs[t])
        dWf += np.dot(df, zs[t].T)
        dbf += np.sum(df, axis=-1, keepdims=True)

        # gradient of the combined input z
        dz = (
            np.dot(Wo.T, do) + np.dot(Wc.T, dcand) + np.dot(Wi.T, di) + np.dot(Wf.T, df)
        )

        # update dh_next and dc_next for the next iteration
        dc_next = fs[t] * dc
        dh_next = dz[:hidden_size]

        # gradient of the input x
        dWex += np.dot(dz[hidden_size:], xs[t].T)

    # clip to mitigate exploding gradients
    if clipping:
        for dparam in [dWex, dWf, dWi, dWo, dWc, dbf, dbi, dbo, dbc, dWhy, dby]:
            np.clip(dparam, -1, 1, out=dparam)

    gradients = (dWex, dWf, dWi, dWo, dWc, dbf, dbi, dbo, dbc, dWhy, dby)

    return gradients


def sample(memory, seed_ix, n):
    """
  sample a sequence of integers from the model
  h is memory state, seed_ix is seed letter for first time step
  """
    h, c = memory
    x = np.zeros((vocab_size, 1))
    x[seed_ix] = 1
    ixes = []
    for t in range(n):
        # forward pass again, but we do not have to store the activations now
        we = np.dot(Wex, x)
        z = np.row_stack((h, we))
        f = sigmoid(np.dot(Wf, z) + bf)
        ins = sigmoid(np.dot(Wi, z) + bi)
        c_ = np.tanh(np.dot(Wc, z) + bc)
        c = f * c + ins * c_
        o = sigmoid(np.dot(Wo, z) + bo)
        h = o * np.tanh(c)
        y = np.dot(Why, h) + by
        p = softmax(y)
        # p = np.exp(y) / np.sum(np.exp(y))
        ix = np.random.choice(range(vocab_size), p=p.ravel())

        index = ix
        x = np.zeros((vocab_size, 1))
        x[index] = 1
        ixes.append(index)
    return ixes


if option == "train":

    n, p = 0, 0
    n_updates = 0

    # momentum variables for Adagrad
    mWex, mWhy = np.zeros_like(Wex), np.zeros_like(Why)
    mby = np.zeros_like(by)

    mWf, mWi, mWo, mWc = (
        np.zeros_like(Wf),
        np.zeros_like(Wi),
        np.zeros_like(Wo),
        np.zeros_like(Wc),
    )
    mbf, mbi, mbo, mbc = (
        np.zeros_like(bf),
        np.zeros_like(bi),
        np.zeros_like(bo),
        np.zeros_like(bc),
    )

    smooth_loss = -np.log(1.0 / vocab_size) * seq_length  # loss at iteration 0

    data_length = cut_stream.shape[1]

    while True:
        # prepare inputs (we're sweeping from left to right in steps seq_length long)
        if p + seq_length + 1 >= data_length or n == 0:
            hprev = np.zeros((hidden_size, batch_size))  # reset RNN memory
            cprev = np.zeros((hidden_size, batch_size))
            p = 0  # go from start of data

        inputs = cut_stream[:, p : p + seq_length].T
        targets = cut_stream[:, p + 1 : p + 1 + seq_length].T

        # sample from the model now and then
        if n % 200 == 0:
            h_zero = np.zeros((hidden_size, 1))  # reset RNN memory
            c_zero = np.zeros((hidden_size, 1))
            sample_ix = sample((h_zero, c_zero), inputs[0][0], 2000)
            txt = "".join(ix_to_char[ix] for ix in sample_ix)
            print("----\n %s \n----" % (txt,))

        # forward seq_length characters through the net and fetch gradient
        loss, activations, memory = forward(inputs, targets, (hprev, cprev))
        hprev, cprev = memory
        gradients = backward(activations)

        dWex, dWf, dWi, dWo, dWc, dbf, dbi, dbo, dbc, dWhy, dby = gradients
        smooth_loss = smooth_loss * 0.999 + loss / batch_size * 0.001
        if n % 20 == 0:
            print("iter %d, loss: %f" % (n, smooth_loss))  # print progress

        if n % 100 == 0:
            # save prediction to file
            with open(f"predictions/prediction_iter{n}.txt", "w+") as f:
                f.write(f"Prediction iter: {n} \n Loss: {smooth_loss} \n \n {txt}")

        # perform parameter update with Adagrad
        for param, dparam, mem in zip(
            [Wf, Wi, Wo, Wc, bf, bi, bo, bc, Wex, Why, by],
            [dWf, dWi, dWo, dWc, dbf, dbi, dbo, dbc, dWex, dWhy, dby],
            [mWf, mWi, mWo, mWc, mbf, mbi, mbo, mbc, mWex, mWhy, mby],
        ):
            mem += dparam * dparam
            param += -learning_rate * dparam / np.sqrt(mem + 1e-8)  # adagrad update

        p += seq_length  # move data pointer
        n += 1  # iteration counter
        n_updates += 1
        if n_updates >= max_updates or n_updates >= epochs:
            break


elif option == "gradcheck":

    data_length = cut_stream.shape[1]

    p = 0
    # inputs = [char_to_ix[ch] for ch in data[p:p + seq_length]]
    # targets = [char_to_ix[ch] for ch in data[p + 1:p + seq_length + 1]]
    inputs = cut_stream[:, p : p + seq_length].T
    targets = cut_stream[:, p + 1 : p + 1 + seq_length].T

    delta = 0.0001

    hprev = np.zeros((hidden_size, batch_size))
    cprev = np.zeros((hidden_size, batch_size))

    memory = (hprev, cprev)

    loss, activations, hprev = forward(inputs, targets, memory)
    gradients = backward(activations, clipping=False)
    dWex, dWf, dWi, dWo, dWc, dbf, dbi, dbo, dbc, dWhy, dby = gradients

    for weight, grad, name in zip(
        [Wf, Wi, Wo, Wc, bf, bi, bo, bc, Wex, Why, by],
        [dWf, dWi, dWo, dWc, dbf, dbi, dbo, dbc, dWex, dWhy, dby],
        ["Wf", "Wi", "Wo", "Wc", "bf", "bi", "bo", "bc", "Wex", "Why", "by"],
    ):

        str_ = "Dimensions dont match between weight and gradient %s and %s." % (
            weight.shape,
            grad.shape,
        )
        assert weight.shape == grad.shape, str_

        print(name)
        countidx = 0
        gradnumsum = 0
        gradanasum = 0
        relerrorsum = 0
        erroridx = []

        for i in range(weight.size):

            # evaluate cost at [x + delta] and [x - delta]
            w = weight.flat[i]
            weight.flat[i] = w + delta
            loss_positive, _, _ = forward(inputs, targets, memory)
            weight.flat[i] = w - delta
            loss_negative, _, _ = forward(inputs, targets, memory)
            weight.flat[i] = w  # reset old value for this parameter
            # fetch both numerical and analytic gradient
            grad_analytic = grad.flat[i]
            grad_numerical = (loss_positive - loss_negative) / (2 * delta)
            gradnumsum += grad_numerical
            gradanasum += grad_analytic
            rel_error = abs(grad_analytic - grad_numerical) / abs(
                grad_numerical + grad_analytic
            )
            if rel_error is None:
                rel_error = 0.0
            relerrorsum += rel_error

            if rel_error > 0.001:
                print(
                    "WARNING %f, %f => %e " % (grad_numerical, grad_analytic, rel_error)
                )
                countidx += 1
                erroridx.append(i)

        print(
            "For %s found %i bad gradients; with %i total parameters in the vector/matrix!"
            % (name, countidx, weight.size)
        )
        print(
            " Average numerical grad: %0.9f \n Average analytical grad: %0.9f \n Average relative grad: %0.9f"
            % (
                gradnumsum / float(weight.size),
                gradanasum / float(weight.size),
                relerrorsum / float(weight.size),
            )
        )
        print(
            " Indizes at which analytical gradient does not match numerical:", erroridx
        )
