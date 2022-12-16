import glob
import os
import sys

import toml
import numpy as np
import shutil
import inspect

from lasif.tools.query_gcmt_catalog import get_random_mitchell_subset
from optson.base_classes.model import ModelStochastic

from inversionson import InversionsonError
from inversionson.helpers.regularization_helper import RegularizationHelper
from inversionson.optimizers.optimizer import Optimize
from inversionson.utils import write_xdmf
from salvus.mesh.unstructured_mesh import UnstructuredMesh as um


class OptsonLink(Optimize):
    """
    A class that acts as a bridge to Optson.

    #TODO: Add smoothing
    #TODO: Clean up old iterations
    #TODO optimize calls to control group misfit/gradient.

    # Simply perform the mini-batch job first, and then call control group.
    # in this way adjoint jobs will be submitted already, so the next call will
    # be quick.
    #TODO: Add flag to iteration listerener that does misfit only, but still submits the adjoint jobs

    # Become smarter about the jobs. For example when gx_cg_prev is called, we know
    the model is accepted. we can run the iteration listener with all_events.
    # then we can for cg_prev, also already immediately smooth the mini-batch gradient,
    the new control group gradient and the previous gradient.
    #
    """
    optimizer_name = "Optson"
    config_template_path = os.path.join(
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(inspect.getfile(inspect.currentframe())))
        ),
        "file_templates",
        "Optson.toml"
    )
    current_iteration_name = "x_00000"
    def __init__(self, comm):

        # Call the super init with all the common stuff
        super().__init__(comm)
        self.opt = None

    def _initialize_derived_class_folders(self):
        """These folder are needed only for Optson."""
        self.smooth_gradient_dir = self.opt_folder / "SMOOTHED_GRADIENTS"

    def get_smooth_gradient_path(self, model_name, set_flag: str = "mb"):
        allowed_set_flags = ["mb", "cg", "cg_prev"]
        if set_flag not in allowed_set_flags:
            raise Exception(f"Only {allowed_set_flags} can be passed")
        return self.smooth_gradient_dir / f"smooth_g_{set_flag}_{model_name}.h5"

    def get_raw_gradient_path(self, model_name, set_flag: str = "mb"):
        allowed_set_flags = ["mb", "cg", "cg_prev"]
        if set_flag not in allowed_set_flags:
            raise Exception(f"Only {allowed_set_flags} can be passed")
        return self.raw_gradient_dir / f"raw_g_{set_flag}_{model_name}.h5"

    @property
    def status_file(self):
        return str(self.opt_folder / "optson_status_tracker.json")

    @property
    def gradient_norm_path(self):
        return (
            self.gradient_norm_dir / f"gradient_norms_{self.iteration_number:05d}.toml"
        )

    @staticmethod
    def _get_path_for_iteration(iteration_number, path):
        filename = path.stem
        separator = "_"
        reconstructed_filename = (
            separator.join(filename.split("_")[:-1])
            + f"_{iteration_number:05d}"
            + path.suffix
        )
        return path.parent / reconstructed_filename

    # def vector_to_mesh(self, to_mesh, m):
    #     """
    #     Maps an Optson vector to a salvus mesh.
    #     # TODO: add option for multiple parameters.
    #     """
    #     print("start vector_to_mesh")
    #     # all_parameters = self.parameters
    #     m_init = um.from_h5(self.initial_model)
    #     normalization = True
    #     if normalization:
    #         m_init.element_nodal_fields["VSV"][:] = m_init.element_nodal_fields[
    #                                                     "VSV"][:] * m.x[
    #                                                     m_init.connectivity]
    #     else:
    #         m_init.element_nodal_fields["VSV"][:] = m.x[m_init.connectivity]
    #     m_init.write_h5(to_mesh)
    #     print("end_vector_to_mesh")
    # def vector_to_mesh(self, to_mesh, m):
    #     parameters = ["VSV", "VSH"]
    #     par_vals = np.array_split(m.x, len(parameters))
    #     m_init = um.from_h5(self.initial_model)
    #
    #     for idx, par in enumerate(parameters):
    #         normalization = True
    #         if normalization:
    #             m_init.element_nodal_fields[par][:] = \
    #             m_init.element_nodal_fields[
    #                 par][:] * par_vals[idx][
    #                 m_init.connectivity]
    #         else:
    #             m_init.element_nodal_fields[par][:] = par_vals[idx][
    #                 m_init.connectivity]
    #     m_init.write_h5(to_mesh)

    # def mesh_to_vector(self, mesh_filename, gradient=True, raw_grad_file=None):
    #     parameters = ["VSV", "VSH"]
    #     m = um.from_h5(mesh_filename)
    #     m_init = um.from_h5(self.initial_model)
    #
    #     if gradient:
    #         rg = um.from_h5(raw_grad_file)
    #         mm = rg.element_nodal_fields["FemMassMatrix"]
    #         valence = rg.element_nodal_fields["Valence"]
    #
    #     _, i = np.unique(m.connectivity, return_index=True)
    #
    #     normalization = True
    #     # par_dict = {}
    #     par_list = []
    #     for par in parameters:
    #         if normalization:
    #             if gradient:
    #                 par_val = m.element_nodal_fields[par] * \
    #                           m_init.element_nodal_fields[par]
    #             else:
    #                 par_val = m.element_nodal_fields[par] / \
    #                           m_init.element_nodal_fields[par]
    #         else:
    #             par_val = m.element_nodal_fields[par]
    #
    #         if gradient:
    #             par_val = par_val * mm * valence  # multiply with valence to account for duplication.
    #         # par_dict[par] = par_val.flatten()[i]
    #         par_list.append(par_val.flatten()[i])
    #
    #     v = np.concatenate(par_list)
    #     return v

    def vector_to_mesh(self, to_mesh, m):
        parameters = ["VSV", "VSH"]
        points = self.get_points(self.initial_model)
        nelem = points.shape[0]
        ngll = points.shape[1]
        ndim = 3
        par_vals = np.array_split(m.x, len(parameters))
        _, pt_idcs, inv_pt_idcs = np.unique(
            points.reshape(nelem, ngll, ndim),
            return_index=True, return_inverse=True, axis=0)

        m_init = self.get_flat_non_duplicated_data(
            parameters, self.initial_model,pt_idcs)

        par_list = []
        for idx, _ in enumerate(parameters):
            normalization = True
            if normalization:
                m_init[idx] = m_init[idx] * par_vals[idx]
            else:
                m_init[idx] = m_init[idx] * par_vals[idx]
            # now shape to original form
            par = m_init[idx][inv_pt_idcs]
            par = par.reshape((nelem, ngll))
            par_list.append(par)
        data_in_original_shape = np.stack(par_list, axis=1)
        shutil.copy(self.initial_model, to_mesh)
        self.set_h5_data(to_mesh, data_in_original_shape, create_xdmf=True)

    def mesh_to_vector(self, mesh_filename, gradient=True, raw_grad_file=None):
        parameters = ["VSV", "VSH"]
        points = self.get_points(mesh_filename)
        _, pt_idcs = np.unique(
            points.reshape(points.shape[0] * points.shape[1], points.shape[2]),
            return_index=True, axis=0)

        if gradient:
            mm, valence = self.get_flat_non_duplicated_data(
                ["FemMassMatrix", "Valence"], raw_grad_file, pt_idcs)

        mesh_data = self.get_flat_non_duplicated_data(
            parameters, mesh_filename, pt_idcs)
        initial_data = self.get_flat_non_duplicated_data(
            parameters, self.initial_model, pt_idcs)

        normalization = True
        # par_dict = {}
        par_list = []
        for idx, par in enumerate(parameters):
            if normalization:
                if gradient:
                    par_val = mesh_data[idx] * initial_data[idx]
                else:
                    par_val = mesh_data[idx] / initial_data[idx]
            else:
                par_val = mesh_data[idx]

            if gradient:
                par_val = par_val * mm * valence  # multiply with valence to account for duplication.
            # par_dict[par] = par_val.flatten()[i]
            par_list.append(par_val)
        v = np.concatenate(par_list)
        return v

    # def mesh_to_vector(self, mesh_filename, gradient=True, raw_grad_file=None):
    #     """
    #     Maps a salvus mesh to a vector suitable for use with Optson.
    #     #TODO: add option for multiple parameters.
    #     """
    #     print("start mesh to vector")
    #     m = um.from_h5(mesh_filename)
    #     m_init = um.from_h5(self.initial_model)
    #     _, i = np.unique(m.connectivity, return_index=True)
    #
    #     normalization = True
    #     # Normalization, still have to make the case with zero velocity work
    #     # TODO: fix case with velocities of zero, simply catch exception and replace with zero or 1
    #     if normalization:
    #         if gradient:
    #             vsv = m.element_nodal_fields["VSV"] * \
    #                   m_init.element_nodal_fields["VSV"]
    #         else:
    #             vsv = m.element_nodal_fields["VSV"] / \
    #                   m_init.element_nodal_fields["VSV"]
    #     else:
    #         vsv = m.element_nodal_fields["VSV"]
    #
    #     # Gradient, this also implies the mesh filename is a gradient
    #     # and thus has the FemMassMatrix and Valence fields.
    #     if gradient:
    #         rg = um.from_h5(raw_grad_file)
    #         mm = rg.element_nodal_fields["FemMassMatrix"]
    #         valence = rg.element_nodal_fields["Valence"]
    #         vsv = vsv * mm * valence  # multiply with valence to account for duplication.
    #     v = vsv.flatten()[i]
    #     print("end mesh to vector")
    #     return v

    def perform_task(self, verbose=True):
        """
        Task manager calls this class. Main entry point. Here, all the magic will happen.
        """
        from optson.optimize import Optimize
        from optson.methods.trust_region_LBFGS import StochasticTrustRegionLBFGS
        from optson.methods.steepest_descent import StochasticSteepestDescent
        from inversionson.optimizers.StochasticFWI import StochasticFWI
        self.find_iteration_numbers()
        if self.do_gradient_test:
            self.gradient_test()
            sys.exit()

        problem = StochasticFWI(comm=self.comm, optlink=self,
                                batch_size=1, status_file=self.status_file)

        steepest_descent = StochasticSteepestDescent(
            initial_step_length=3e-2,
            verbose=verbose,
            step_length_as_percentage=True)
        method = StochasticTrustRegionLBFGS(
            steepest_descent=steepest_descent,
            verbose=verbose)

        x_0 = self.mesh_to_vector(self.initial_model, gradient=False)
        self.opt = Optimize(x_0=x_0, problem=problem, method=method)
        self.opt.iterate(self.max_iterations)

    def gradient_test(self, h=None):
        """
        Function to perform a gradient test for the current project.
        from a notebook in the root directory of inversionson, you may call this
        like this in the following way:

            from inversionson.autoinverter import read_info_toml, AutoInverter
            info = read_info_toml("")
            auto = AutoInverter(info, manual_mode=True)
            auto.move_files_to_cluster()
            opt = auto.comm.project.get_optimizer()
            grd_test = opt.gradient_test()

        """
        from inversionson.optimizers.StochasticFWI import StochasticFWI
        if not h:
            h = np.logspace(-7, -1, 7)
        print("All these h values that will be tested:", h)
        problem = StochasticFWI(comm=self.comm, optlink=self,
                                batch_size=1, gradient_test=True,
                                status_file=self.status_file)
        from optson.gradient_test import GradientTest

        x_0 = self.mesh_to_vector(self.initial_model, gradient=False)
        grdtest = GradientTest(x_0=x_0, h=h,
                               problem=problem)

        import matplotlib.pyplot as plt
        plt.loglog(grdtest.h, grdtest.relative_errors)
        plt.title(f"Minimum relative error: {min(grdtest.relative_errors)}")
        plt.xlabel("h")
        plt.ylabel("Relative error")
        plt.savefig("gradient_test.png")
        return grdtest

    def find_iteration_numbers(self):
        models = glob.glob(f"{self.model_dir}/*.h5")
        if len(models) == 0:
            return [0]
        iteration_numbers = []
        for model in models:
            it_number = int(model.split("/")[-1].split(".")[0].split("_")[2])
            if it_number not in iteration_numbers:
                iteration_numbers.append(it_number)
        iteration_numbers.sort()
        return iteration_numbers

    @property
    def model_path(self, iteration_name=None):
        if not iteration_name:
            return self.model_dir / f"model_{self.current_iteration_name}.h5"
        else:
            return self.model_dir / f"model_{iteration_name}.h5"

    def _read_config(self):
        """Reads the config file."""
        if not os.path.exists(self.config_file):
            raise Exception("Can't read the SGDM config file")
        config = toml.load(self.config_file)

        self.initial_model = config["initial_model"]
        self.smoothing_timestep = config["smoothing_timestep"]
        self.gradient_smoothing_length = config["gradient_smoothing_length"]
        self.do_gradient_test = config["do_gradient_test"]
        self.max_iterations = config["max_iterations"]

        if "max_iterations" in config.keys():
            self.max_iterations = config["max_iterations"]
        else:
            self.max_iterations = None

    def _init_directories(self):
        """
        Build directory structure.
        """
        folders = [
            self.model_dir,
            self.average_model_dir,
            self.smooth_gradient_dir,
            self.raw_gradient_dir,
            self.regularization_dir,
            self.gradient_norm_dir,
        ]

        for folder in folders:
            if not os.path.exists(folder):
                os.mkdir(folder)

        shutil.copy(self.initial_model, self.model_path)
        write_xdmf(self.model_path)

    def _finalize_iteration(self, verbose: bool):
        pass
        # """
        # Here we can do some documentation. Maybe just call a base function for that
        # """
        # super().delete_remote_files()
        # self.comm.storyteller.document_task(task="adam_documentation")

    def pick_data_for_iteration(self, batch_size, prev_control_group=[],
                                current_batch=[],
                                select_new_control_group=False,
                                control_group_size: int = None):

        all_events = self.comm.lasif.list_events()
        blocked_data = set(self.comm.project.validation_dataset +
                           self.comm.project.test_dataset
                           + prev_control_group)
        all_events = list(set(all_events) - blocked_data)
        n_events = batch_size - len(prev_control_group)
        events = []

        if select_new_control_group:
            if not current_batch:
                raise Exception("I need the current batch if you want"
                                "a control group to be selected.")
            all_events = current_batch
            if not control_group_size:
                control_group_size = int(np.ceil(0.5*len(current_batch)))
            n_events = control_group_size

        all_norms_path = self.gradient_norm_dir / "all_norms.toml"

        if n_events > 0: # for edge case batch size is same length as prev control group
            if os.path.exists(all_norms_path):
                norm_dict = toml.load(all_norms_path)
                unused_events = list(set(all_events).difference(set(norm_dict.keys())))
                list_of_vals = np.array(list(norm_dict.values()))
                # Set unused to 65%, so slightly above average
                max_norm = np.max(list_of_vals)

                # Assign high norm values to unused events to make them
                # more likely to be chosen
                for event in unused_events:
                    norm_dict[event] = max_norm
                events = get_random_mitchell_subset(
                    self.comm.lasif.lasif_comm, n_events, all_events, norm_dict
                )
            else:
                events = get_random_mitchell_subset(
                    self.comm.lasif.lasif_comm, n_events, all_events
                )

        if self.time_for_validation() and not select_new_control_group:
            print(
                "This is a validation iteration. Will add validation events to the iteration"
            )
            events += self.comm.project.validation_dataset
        events += prev_control_group

        return events

    def pick_control_group(self):
        pass

    def prepare_iteration(self, events, iteration_name=None):
        iteration_name = iteration_name if iteration_name else self.iteration_name
        if self.comm.lasif.has_iteration(iteration_name):
            self.comm.project.change_attribute("current_iteration",
                                               iteration_name)
            self.comm.project.get_iteration_attributes(iteration=iteration_name)
            return
        self.comm.project.change_attribute("current_iteration", iteration_name)
        self.print("Picking data for iteration")

        # this should become smart with control groups etc.
        super().prepare_iteration(it_name=iteration_name, events=events)

    def perform_smoothing(self, m: ModelStochastic, set_flag, file):
        """
        Todo, if control group getx extended, this should be reset.
        """
        tasks = {}
        tag = file.name
        output_location = self.get_smooth_gradient_path(m.name, set_flag=set_flag)
        if max(self.gradient_smoothing_length) > 0.0:
            tasks[tag] = {
                "reference_model": str(self.comm.lasif.get_master_model()),
                "model_to_smooth": str(file),
                "smoothing_lengths": self.gradient_smoothing_length,
                "smoothing_parameters": self.parameters,
                "output_location": str(output_location),
            }
        else:
            shutil.copy(file, output_location)

        if len(tasks.keys()) > 0:
            reg_helper = RegularizationHelper(
                comm=self.comm, iteration_name=m.name, tasks=tasks,
                optimizer=self
            )
            if tag in reg_helper.tasks.keys() and not os.path.exists(output_location):
                # remove the completed tag if we need to redo smoothing.
                reg_helper.tasks[tag].update(reg_helper.base_dict)
                reg_helper._write_tasks(reg_helper.tasks)

            reg_helper.monitor_tasks()

        write_xdmf(str(output_location))

    def compute_gradient(self, verbose):
        pass