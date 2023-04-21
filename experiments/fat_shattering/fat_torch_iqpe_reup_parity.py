import argparse
import yaml
import os
import uuid
import time
import datetime
import json
import torch
import pennylane as qml
from qml_mor.models import IQPEReuploadSU2Parity
from qml_mor.fat import fat_shattering_dim, normalize_const
from qml_mor.datagen import DataGenFat
from qml_mor.optimize import AdamTorch


def parse_args():
    # Read the configuration file
    with open("cfg_fat.yaml", "r") as f:
        config = yaml.safe_load(f)

    parser = argparse.ArgumentParser(
        description="Process arguments for QML-MOR fat shattering experiments"
    )
    parser.add_argument(
        "--dmin",
        type=int,
        default=config["dmin"],
        help="Minimum value of d for experiments",
    )
    parser.add_argument(
        "--dmax",
        type=int,
        default=config["dmax"],
        help="Maximum value of d for experiments (included)",
    )
    parser.add_argument(
        "--dstep",
        type=int,
        default=config["dstep"],
        help="Step size for d in experiments",
    )
    parser.add_argument(
        "--gamma",
        type=float,
        default=config["gamma"],
        help="Margin value for fat shattering",
    )
    parser.add_argument(
        "--gamma_fac",
        type=float,
        default=config["gamma_fac"],
        help="Additional multiplicative factor for margin value",
    )
    parser.add_argument(
        "--num_qubits",
        type=int,
        default=config["num_qubits"],
        help="Number of qubits in QNN",
    )
    parser.add_argument(
        "--num_reups",
        type=int,
        default=config["num_reups"],
        help="Number of data reuploads in QNN",
    )
    parser.add_argument(
        "--num_layers",
        type=int,
        default=config["num_layers"],
        help="Number of variational layers in QNN",
    )
    parser.add_argument(
        "--omega",
        type=float,
        default=config["omega"],
        help="The exponential feature scaling factor",
    )
    parser.add_argument(
        "--Sb",
        type=int,
        default=config["Sb"],
        help="Number of binary samples to check shattering",
    )
    parser.add_argument(
        "--Sr",
        type=int,
        default=config["Sr"],
        help="number of level offset samples to check shattering",
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=config["lr"],
        help="Learning rate",
    )
    parser.add_argument(
        "--amsgrad",
        type=bool,
        default=config["amsgrad"],
        help="Use amsgrad",
    )
    parser.add_argument(
        "--opt_steps",
        type=int,
        default=config["opt_steps"],
        help="Number of optimization steps",
    )
    parser.add_argument(
        "--opt_stop",
        type=float,
        default=config["opt_stop"],
        help="Convergence threshold for optimization",
    )
    parser.add_argument(
        "--early_stop",
        type=bool,
        default=config["early_stop"],
        help="Stops iterations early if the previous capacity is at least as large",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=config["seed"],
        help="Random seed for generating dataset",
    )
    parser.add_argument(
        "--save_dir",
        type=str,
        default=config["save_dir"],
        help="Directory for saving results",
    )
    parser.add_argument(
        "--cuda",
        type=bool,
        default=config["cuda"],
        help="Set to true if simulations are run on a GPU",
    )
    args = parser.parse_args()
    return args


def main(args):
    # Define QNN model
    num_qubits = args.num_qubits
    num_layers = args.num_layers
    num_reups = args.num_reups
    omega = args.omega
    seed = args.seed
    cuda = args.cuda

    if seed is not None:
        torch.manual_seed(seed)

    cdevice = torch.device("cpu")
    if cuda:
        cdevice = torch.device("cuda")

    init_theta = torch.randn(num_reups, num_qubits, requires_grad=True).to(cdevice)
    theta = torch.randn(
        num_reups, num_layers, num_qubits - 1, 2, requires_grad=True
    ).to(cdevice)
    W = torch.randn(2**num_qubits, requires_grad=True).to(cdevice)
    params = [init_theta, theta, W]

    qnn_model = IQPEReuploadSU2Parity(params, omega)

    # Define qnode
    shots = None
    qdevice = qml.device("lightning.qubit", wires=args.num_qubits, shots=shots)
    if cuda:
        qdevice = qml.device("lightning.gpu", wires=args.num_qubits, shots=shots)
    qnode = qml.QNode(qnn_model.qfunction, qdevice, interface="torch")

    # Set optimizer
    loss_fn = torch.nn.MSELoss()
    opt = AdamTorch(
        params=params,
        loss_fn=loss_fn,
        lr=args.lr,
        amsgrad=args.amsgrad,
        opt_steps=args.opt_steps,
        opt_stop=args.opt_stop,
    )

    # Set data generating method
    sizex = num_qubits
    Sb = args.Sb
    Sr = args.Sr
    gamma = args.gamma
    gamma_fac = args.gamma_fac
    datagen = DataGenFat(
        sizex=sizex, Sb=Sb, Sr=Sr, gamma=gamma_fac * gamma, seed=seed, device=cdevice
    )

    # Estimate capacity
    dmin = args.dmin
    dmax = args.dmax
    dstep = args.dstep

    start_time = time.time()
    fat_dim = fat_shattering_dim(
        model=qnode,
        datagen=datagen,
        opt=opt,
        dmin=dmin,
        dmax=dmax,
        gamma=gamma,
        dstep=dstep,
    )
    end_time = time.time()
    time_taken = end_time - start_time

    # Save results
    clock = datetime.datetime.now().strftime("%H:%M:%S")
    date = datetime.date.today().strftime("%d/%m/%Y")
    creation_date = date + ", " + clock

    num_params_gates = torch.numel(init_theta) + torch.numel(theta)
    num_params_obs = torch.numel(W)
    num_params = num_params_gates + num_params_obs

    norm = normalize_const(weights=W, gamma=gamma, Rx=sizex)

    results = {
        "date": creation_date,
        "time_taken": time_taken,
        "num_qubits": args.num_qubits,
        "num_layers": args.num_layers,
        "num_reups": args.num_reups,
        "omega": omega,
        "dmin": dmin,
        "dmax": dmax,
        "dstep": dstep,
        "gamma": gamma,
        "gamma_fac": gamma_fac,
        "num_params_gates": num_params_gates,
        "num_params_obs": num_params_obs,
        "num_params": num_params,
        "Sb": Sb,
        "Sr": Sr,
        "opt_steps": args.opt_steps,
        "opt_stop": args.opt_stop,
        "seed": seed,
        "fat_dim": fat_dim,
        "fat_dim_norm": fat_dim / norm,
    }
    exp_id = str(uuid.uuid4())
    direc = args.save_dir
    filename = os.path.join(direc, exp_id + ".json")
    with open(filename, "w") as f:
        json.dump(results, f)


if __name__ == "__main__":
    args = parse_args()
    main(args)
