from optson.optimizer import Optimizer
from optson.methods import AdamUpdate, BasicTRUpdate, SteepestDescentUpdate
from optson.stopping_criterion import BasicStoppingCriterion
from optson.monitor import BasicMonitor
from inversionson.problem import Problem
from inversionson.utils import mesh_to_vector
from inversionson.project import Project
from inversionson.problem import InversionsonAdamUpdatePrecondtioner
from inversionson.batch_manager import InversionsonBatchManager
import numpy as np
import matplotlib.pyplot as plt
import sys


SC = BasicStoppingCriterion(
    tolerance=1e-100, divergence_tolerance=1e100, max_iterations=99999
)
MONITOR = BasicMonitor(step=1)


def get_adam_opt(project: Project) -> Optimizer:
    """Inversionson with Adam optimization."""
    ibm = InversionsonBatchManager(
        project=project,
        batch_size=project.config.inversion.initial_batch_size,
        use_overlapping_batches=False,
    )
    problem = Problem(project=project, smooth_gradients=False)
    update_precond = InversionsonAdamUpdatePrecondtioner(project=project)
    ad_upd = AdamUpdate(
        alpha=0.005, epsilon=0.1, relative_epsilon=True, preconditioner=update_precond
    )
    return Optimizer(
        problem=problem,
        update=ad_upd,
        stopping_criterion=SC,
        monitor=MONITOR,
        state_file=project.paths.optson_state_file,
        batch_manager=ibm,
    )


def get_dynamic_mini_batch_opt(project: Project):
    "Inversionson with dynamic mini-batches"
    ibm = InversionsonBatchManager(
        project=project,
        batch_size=project.config.inversion.initial_batch_size,
        use_overlapping_batches=True,
    )
    problem = Problem(project=project, smooth_gradients=True)
    st_upd = SteepestDescentUpdate(
        initial_step_size=0.05, initial_step_as_percentage=True, verbose=True
    )
    update = BasicTRUpdate(fallback=st_upd, verbose=True)
    return Optimizer(
        problem=problem,
        update=update,
        stopping_criterion=SC,
        monitor=MONITOR,
        state_file=project.paths.optson_state_file,
        batch_manager=ibm,
    )


def gradient_test(project: Project):
    from optson.gradient_test import GradientTest

    x0 = mesh_to_vector(
        project.lasif.master_mesh,
        params_to_invert=project.config.inversion.inversion_parameters,
    )
    h = np.logspace(-7, -1, 7)
    problem = Problem(project=project, smooth_gradients=False)
    gt = GradientTest(x0=x0, h=h, problem=problem, verbose=True)
    gt.plot()
    plt.savefig("gradient_test.png")


def run_optson(project: Project):
    """
    This function is called by Inversionson and runs Optson.
    """
    do_gradient_test = False
    if do_gradient_test:
        gradient_test(project)
        sys.exit()

    # Choose a version of the Optimizer or implememt your own
    # opt = get_adam_opt(project)
    opt = get_dynamic_mini_batch_opt(project)
    opt.iterate(
        x0=mesh_to_vector(
            project.lasif.master_mesh,
            params_to_invert=project.config.inversion.inversion_parameters,
        )
    )
