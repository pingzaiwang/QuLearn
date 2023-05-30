import os
import tempfile
import torch
from torch.nn import Linear
from torch.optim import Adam
from typing import List
from qulearn.qlayer import IQPEmbeddingLayer, RYCZLayer, HamiltonianLayer
from qulearn.observable import parities_all_observables
from qulearn.memory import memory, fit_rand_labels
from qulearn.datagen import DataGenCapacity
from qulearn.trainer import RegressionTrainer


def test_capacity_qnn():
    Nmin = 1
    Nmax = 3
    num_samples = 2

    num_qubits = 3
    num_reups = 1
    num_layers = 1
    sizex = num_qubits

    datagen = DataGenCapacity(sizex=sizex, num_samples=num_samples)

    # QNN model
    embed = IQPEmbeddingLayer(num_qubits, n_repeat=num_reups)
    var = RYCZLayer(num_qubits, n_layers=num_layers)
    observables = parities_all_observables(num_qubits)
    model = HamiltonianLayer(embed, var, observables=observables)

    loss_fn = torch.nn.MSELoss()
    opt = Adam(model.parameters(), lr=0.1, amsgrad=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "model")
        trainer = RegressionTrainer(opt, loss_fn, num_epochs=20, file_name=path)
        C = memory(model, datagen, trainer, Nmin, Nmax)
        assert isinstance(C, List)
        assert C[0][3] <= 100
        assert C[0][3] >= 0


def test_capacity_linear():
    num_samples = 10

    sizex = 3

    Nmin = sizex - 2
    Nmax = sizex + 2
    seed = 0

    datagen = DataGenCapacity(sizex=sizex, num_samples=num_samples, seed=seed)
    loss_fn = torch.nn.MSELoss()
    model = Linear(sizex, 1, dtype=torch.float64)
    opt = Adam(model.parameters(), lr=0.1, amsgrad=True)
    trainer = RegressionTrainer(opt, loss_fn, num_epochs=500, best_loss=False)
    C = memory(model, datagen, trainer, Nmin, Nmax, stop_count=2)

    assert isinstance(C, List)
    assert C[0][3] >= 0
    assert len(C) >= 4
    assert C[3][3] >= C[4][3]


def test_fit_labels():
    N = 3
    sizex = 2
    num_samples = 10
    num_qubits = sizex
    num_reups = 1
    num_layers = 1

    datagen = DataGenCapacity(sizex=sizex, num_samples=num_samples)

    # QNN model
    embed = IQPEmbeddingLayer(num_qubits, n_repeat=num_reups)
    var = RYCZLayer(num_qubits, n_layers=num_layers)
    observables = parities_all_observables(num_qubits)
    model = HamiltonianLayer(embed, var, observables=observables)

    loss_fn = torch.nn.MSELoss()
    opt = Adam(model.parameters(), lr=0.1, amsgrad=True)
    trainer = RegressionTrainer(opt, loss_fn, num_epochs=10, best_loss=False)
    mre = fit_rand_labels(model, datagen, trainer, N)

    assert isinstance(mre, float)
