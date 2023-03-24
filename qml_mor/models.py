from abc import ABC, abstractmethod
from typing import List, TypeAlias
import torch
import pennylane as qml

Tensor: TypeAlias = torch.Tensor
QFuncOutput: TypeAlias = qml.measurements.ExpectationMP
Observable: TypeAlias = qml.operation.Observable


class QNNModel(ABC):
    """Abstract base class for a quantum neural network model."""

    def __init__(self, params):
        pass

    @abstractmethod
    def qfunction(self, x, params):
        """Abstract method for the quantum function."""
        pass

    def circuit(self, x, params):
        """Constructs a circuit for a given input and parameters."""
        return self.qfunction(self, x, params)

    @property
    @abstractmethod
    def params(self):
        """Abstract property for the model parameters."""
        pass

    @params.setter
    @abstractmethod
    def params(self, params_):
        """Abstract setter for the model parameters."""
        pass


class IQPEReuploadSU2Parity(QNNModel):
    """
    An IQP embedding circuit with additional SU(2) gates and parity measurements.

    Args:
        params (List[Tensor]): The initial parameters of the circuit. Must be a list of
            three tensors: the initial thetas, the main thetas, and the weights W.
        omega (float, optional): The exponential feature scaling factor.
            Defaults to 0.0.
    """

    def __init__(self, params: List[Tensor], omega: float = 0.0):
        """
        Initializes the IQPE + SU(2) circuit.

        Raises:
            ValueError: If the length of params is not 3.
        """

        if len(params) != 3:
            raise ValueError("Parameters must be a list of 3 tensors")

        self.__params = None
        self.__init_theta = params[0]
        self.__theta = params[1]
        self.__W = params[2]
        self.__omega = omega

    def qfunction(self, x: Tensor, params: List[Tensor]) -> QFuncOutput:
        """
        Returns the expectation value circuit of the Hamiltonian of the circuit given
        the input features and the parameters.

        Args:
            x (Tensor): The input features for the circuit.
            params (List[Tensor]): The parameters for the circuit. Must be a list of
                three tensors: the initial thetas, the main thetas, and the weights W.

        Returns:
            QFuncOutput: The expectation value of the Hamiltonian of the circuit.

        Raises:
            ValueError: If the length of params is not 3.
        """

        if len(params) != 3:
            raise ValueError("Parameters must be a list of 3 tensors")

        init_theta = params[0]
        theta = params[1]
        W = params[2]

        return iqpe_reupload_su2_parity(x, init_theta, theta, W, self.omega)

    @property
    def params(self) -> List[Tensor]:
        """
        Returns the current parameters of the circuit.

        Returns:
            List[Tensor]: The current parameters of the circuit.
        """

        return [self.__init_theta, self.__theta, self.__W]

    @params.setter
    def params(self, params_: List[Tensor]):
        """
        Sets the parameters of the circuit.

        Args:
            params_ (List[Tensor]): The new parameters for the circuit.

        Raises:
            ValueError: If the length of params_ is not 3.
        """

        if len(params_) != 3:
            raise ValueError("Parameters must be a list of 3 tensors")

        self.__init_theta = params_[0]
        self.__theta = params_[1]
        self.__W = params_[2]

    @property
    def omega(self) -> float:
        """
        Returns the current exponential feature scaling factor.

        Returns:
            float: The current exponential feature scaling factor.
        """

        return self.__omega

    @omega.setter
    def omega(self, omega_: float):
        """
        Sets the exponential feature scaling factor.

        Args:
            omega_ (float): The new exponential feature scaling factor.
        """

        self.__omega = omega_


def iqpe_reupload_su2_parity(
    x: Tensor, init_theta: Tensor, theta: Tensor, W: Tensor, omega: float = 0.0
) -> QFuncOutput:
    """
    Quantum function that calculates the expectation value
    of the parity of Pauli Z operators.

    Args:
        x (torch.Tensor): Input tensor of shape (num_qubits,)
        init_theta (torch.Tensor): Initial rotation angles for each qubit,
            of shape (reps, num_qubits)
        theta (torch.Tensor): Rotation angles for each layer and each qubit,
            of shape (reps, num_qubits, 3)
        W (torch.Tensor): Interaction weights of shape (num_qubits, num_qubits)
        omega (float, optional): Exponential feature scaling factor. Defaults to 0.0.

    Returns:
        float: Expectation value of the parity of Pauli Z operators
    """

    shape_init = init_theta.shape
    shape = theta.shape
    if len(shape_init) != 2:
        raise ValueError("Initial theta must be a 2-dim tensor")
    if len(shape) != 4:
        raise ValueError("Theta must be a 4-dim tensor")

    num_qubits = len(x)
    reps = shape_init[0]
    wires = range(num_qubits)

    for layer in range(reps):
        features = 2 ** (omega * layer) * x
        initial_layer_weights = init_theta[layer]
        weights = theta[layer]

        qml.IQPEmbedding(features=features, wires=wires)
        qml.SimplifiedTwoDesign(
            initial_layer_weights=initial_layer_weights,
            weights=weights,
            wires=wires,
        )

    obs = parities(num_qubits)
    H = qml.Hamiltonian(W, obs)

    return qml.expval(H)


def sequence_generator(n: int) -> List[List[int]]:
    """
     Generates all possible binary sequences of length n.

    Args:
        n (int): The length of the binary sequences.

    Returns:
        List[List[int]]: A list of all binary sequences of length n,
            represented as a list of integers.

    """

    if n == 0:
        return [[]]
    else:
        sequences = []
        for sequence in sequence_generator(n - 1):
            sequences.append(sequence + [n - 1])
            sequences.append(sequence)
        return sequences


def parities(n: int) -> List[Observable]:
    """
    Generates a list of observables corresponding to the parity of all
    possible binary combinations of n qubits.

    Args:
        n (int): The number of qubits.

    Returns:
        List[Observable]: A list of observables corresponding to the parity of all
            possible binary combinations of n qubits.

    """

    seq = sequence_generator(n)
    ops = []
    for par in seq:
        if par:
            tmp = qml.PauliZ(par[0])
            if len(par) > 1:
                for i in par[1:]:
                    tmp = tmp @ qml.PauliZ(i)

            ops.append(tmp)

    ops.append(qml.Identity(0))

    return ops
