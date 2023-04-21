from typing import TypeAlias
import warnings
import numpy as np
import torch
import pennylane as qml

from .optimize import Optimizer
from .datagen import DataGenTorch

Tensor: TypeAlias = torch.Tensor
Model: TypeAlias = qml.QNode
Datagen: TypeAlias = DataGenTorch
Opt: TypeAlias = Optimizer


def fat_shattering_dim(
    model: Model,
    datagen: Datagen,
    opt: Opt,
    dmin: int,
    dmax: int,
    gamma: float = 0.0,
    dstep: int = 1,
) -> int:
    """
    Estimate the fat-shattering dimension for a model with a given architecture.

    Args:
        model (Model): The model.
        datagen (Datagen): The (synthetic) data generator.
        opt (Opt): The optimizer.
        dmin (int): Iteration start for dimension check.
        dmax (int): Iteration stop for dimension check (including).
        gamma (float, optional): The margin value.
            Defaults to 0.0 (pseudo-dim).
        gamma_fac (float, optional): Additional multiplicative factor
            to increase margin. Defaults to 1.0.
        dstep (int, optional): Dimension iteration step size.
            Defaults to 1.

    Returns:
        int: The estimated fat-shattering dimension.
    """

    for d in range(dmin, dmax + 1, dstep):
        shattered = check_shattering(model, datagen, opt, d, gamma)

        if not shattered:
            if d == dmin:
                warnings.warn(f"Stopped at dmin = {dmin}.")

            return d - 1

    warnings.warn(f"Reached dmax = {dmax}.")
    return dmax


def check_shattering(
    model: Model, datagen: Datagen, opt: Opt, d: int, gamma: float
) -> bool:
    """
    Check if the model shatters a given dimension d with margin value gamma.

    Args:
        model (Model): The model.
        datagen (Datagen): The (synthetic) data generator.
        opt (Opt): The optimizer.
        d (int): Size of data set to shatter.
        gamma (float): The margin value.

    Returns:
        bool: True if the model shatters a random data set of size d,
            False otherwise.
    """

    data = datagen.gen_data(d)
    X = data["X"]
    Y = data["Y"]
    b = data["b"]
    r = data["r"]

    for sr in range(len(r)):
        shattered = True
        for sb in range(len(b)):
            data_opt = {"X": X, "Y": Y[sr, sb]}
            params = opt.optimize(model, data_opt)
            predictions = torch.stack([model(X[k], params) for k in range(d)])

            for i, pred in enumerate(predictions):
                if b[sb, i] == 1 and not (pred >= r[sr, i] + gamma):
                    shattered = False
                    break
                if b[sb, i] == 0 and not (pred <= r[sr, i] - gamma):
                    shattered = False
                    break

            if not shattered:
                break

        if shattered:
            return True

    return False


def normalize_const(weights: Tensor, gamma: float) -> float:
    """
    Compute a normalization constant given a tensor of weights
    and the margin parameter gamma.

    Args:
        weights (Tensor): Tensor of weights
        gamma (float): Margin parameter.

    Returns:
        float: A positive real-valued normalization constant.
    """

    V = torch.norm(weights, p=1)
    C = (V / gamma) ** 2 * np.log2(V / gamma)

    return C.item()
