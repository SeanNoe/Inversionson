"""
from __future__ import annotations
import os
import time
import toml
from typing import Dict, Optional, Union, List, TYPE_CHECKING

if TYPE_CHECKING:
    from inversionson.project import Project

class PlottingHelper(object):
    """
    this class self updates a raydensity plot for every event 
    used in a iteration during the inversion of a project.
    It also collects misfit information for a multiscale average
    misfit source-receiver plot
    """
    def __init__(
        self,
        project: Project,
        iteration_name: str,
        tasks: Optional[Dict] = None
    ):
        
        self.project = project
        self.site_name = self.project.config.hpc.sitename_smoothing
        self.iteration_name = iteration_name
        self.job_toml = (
            self.project.paths.plot_dir / f"plotting_{iteration_name}.toml"
        )
        if tasks is not None:
            self._write_tasks(tasks)
        if os.path.exists(self.job_toml):
            self.tasks = toml.load(self.job_toml)
        else:
            assert tasks is not None
            self.tasks = tasks

    def print(
        self,
        message: str,
        color: str = "cyan",
        line_above: bool = False,
        line_below: bool = False,
        emoji_alias: Union[str, List[str]] = ":artist:"
    ):
        self.project.storyteller.printer.print(
            message=message,
            color=color,
            line_above=line_above,
            line_below=line_below,
            emoji_alias=emoji_alias
        )

    @property
    def base_dict(self) -> Dict:
        return dict(job_name="", submitted=False, retrieved=False, reposts = 0)
    
    def _write_tasks(self, tasks) -> None:
        """
        This function writes the tasks to file or updates the task file.
        """
        if os.path.exists(
            self.job_toml
        ):  # We add the tasks to the existing tasks if needed
            existing_tasks = toml.load(self.job_toml)
            if tasks:
                for task_name in tasks:
                    # Add the empty task if it does not exist
                    if task_name not in existing_tasks.keys():
                        existing_tasks[task_name] = tasks[task_name]
                        existing_tasks[task_name].update(self.base_dict)
                    else:  # Update existing tasks with passed tasks
                        existing_tasks[task_name].update(tasks[task_name])
                with open(self.job_toml, "w") as fh:
                    toml.dump(existing_tasks, fh)

        elif tasks:
            for task_dict in tasks.values():
                task_dict.update(self.base_dict)
            with open(self.job_toml, "w") as fh:
                toml.dump(tasks, fh)

    def dispatch_plotting_tasks(self):
        plotting_msg = True
        for task_name, task_dict in self.tasks.items():
            if(
                not task_dict["submitted"]
                and task_dict["reposts"] < self.project.config.hpc.max_reposts
            ):
                if plotting_msg:
                    self.print("Dispatching Plotting Tasks")
                    plotting_msg = False

                #sims = self.project.plotter.
                #hpc_cluster = self.project.flow.hpc_cluster

                paths = {}
                paths["REMOTE_PATHS"]["PROCESSED_DATA"] = self.project.remote_paths.proc_data_dir
                paths["REMOTE_PATHS"]["RAYPLOTS"] = self.project.remote_paths.rayplots_dir
                paths["REMOTE_PATHS"]["CURRENT_ITERATION"] = self.project.current_iteration
                #paths["REMOTE_PATHS"]["WINDOWS"] = self.project.remote_paths.window_dir

"""

from __future__ import annotations
import os
from typing import List, TYPE_CHECKING
from .component import Component
from inversionson.components.lasif_comp import LASIF
from pathlib import Path
import toml

#if TYPE_CHECKING:
from inversionson.project import Project

import salvus.flow.api as sapi
from salvus.flow.executors import executor_utils
from salvus.flow.executors import job
import salvus.flow.simple_config as sc  # type: ignore
from salvus.opt import smoothing  # type: ignore


_PLOT_OUTPUT_SCRIPT_PATH = (
    Path(__file__).parent.parent / "remote_scripts" / "raydensity_plotting.py"
)

class Plotter(Component):
    """
    A class which handles all dealings with LASIF Raydensity plotting.
    """

    def __init__(self, project: Project):
        #super().__init__(project)
        """
        This class helps with plotting the raydensity of the current iteration
        This is only for remote plotting
        """
        self.project = project

    def print(
        self,
        message: str,
        color: str = "purple",
        line_above: bool = False,
        line_below: bool = False,
        emoji_alias: Union[str, List[str]] = ":nerd_face:",
    ):
        self.project.storyteller.printer.print(
            message=message,
            color=color,
            line_above=line_above,
            line_below=line_below,
            emoji_alias=emoji_alias,
        )

    def plot_rays(
        self,
    ):
        """
        Plot raydensity on HPC system.
        
        """

        iteration = iteration

        # Connect to cluster
        hpc_cluster = self.project.flow.hpc_cluster

        remote_inversionson_dir = self.project.remote_paths.rayplots_dir
        #remote_output_path = remote_inversionson_dir / 
        remote_script = os.path.join(
                    self.project.remote_paths.rayplots_dir / "raydensity_plotting.py"
                )
        if not hpc_cluster.remote_exists(remote_script):
            print(remote_script)
            print(_PLOT_OUTPUT_SCRIPT_PATH)
            hpc_cluster.remote_put(_PLOT_OUTPUT_SCRIPT_PATH, remote_script)
        
        info = {}
        info["REMOTE_PATHS"]["PROCESSED_DATA"] = self.project.remote_paths.proc_data_dir
        info["REMOTE_PATHS"]["RAYPLOTS"] = self.project.remote_paths.rayplots_dir
        info["REMOTE_PATHS"]["CURRENT_ITERATION"] = self.project.current_iteration

        toml_filename = f"rayplot_{iteration}.toml"
        with open(toml_filename, "w") as fh:
            toml.dump(info, fh)

        # copy toml to HPC and remove locally
        remote_toml = os.path.join(remote_inversionson_dir, toml_filename)
        self.project.flow.safe_put(toml_filename, remote_toml)
        os.remove(toml_filename)

        # Call script
        self.print("Rayplot density plotting of current iteration state started..")
        hpc_cluster.execute_command(f"source {self.project.config.hpc.conda_location}; conda activate {self.project.config.hpc.conda_env_name}; python {remote_script} {remote_toml}")
        self.print("Plotting completed..")



"""
    def _write_and_upload_toml(
        self, toml_filename: str, info_dict: Dict, remote_toml_path: Union[Path, str]
    ) -> None:
        """
        Write a dictionary ato toml and copy to the remote.
        Returns the path on the remote
        """
        with open(toml_filename, "w") as fh:
            toml.dump(info_dict, fh)
        self.project.flow.safe_put(toml_filename, remote_toml_path)
        os.remove(toml_filename)

    

    def get_sims_for_plotting_task(
        self,
    ) -> List[]:
        """
        Writes a batch job to run the rayplotter after each iteration 
        
        """
        hpc_cluster = self.project.flow.hpc_cluster
        iteration = self.project.current_iteration

        sim = []

        toml_filename = f"{iteration}_rayplotting.toml"
        remote_toml = self.project.remote_paths.adj_src_dir / toml_filename
        self._write_and_upload_toml(toml_filename, info, remote_toml)

        remote_script = os.path.join(
                    self.project.remote_paths.rayplots_dir / "raydensity_plotting.py"
                )
        if not hpc_cluster.remote_exists(remote_script):
            print(remote_script)
            print(_PLOT_OUTPUT_SCRIPT_PATH)
            hpc_cluster.remote_put(_PLOT_OUTPUT_SCRIPT_PATH, remote_script)

        #Submit the job

        description = f"Raydensity plotting for iteration {iteration}"

        wall_time = self.project.config.hpc.proc_wall_time

        commands = [
            site_utils.RemoteCommand(
                command="mkdir output", execute_with_mpi=False
            ),
            site_utils.RemoteCommand(
                command=f"python {remote_script} {remote_toml}", execute_with_mpi=False
            )
        ]

        if self.project.config.hpc.conda_env_name:
            conda_command = [
                exectuor_utils.RemoteCommand(
                    command=f"conda activate {self.project.config.hpc.conda_env_name}",
                    execute_with_mpi=False,
                )
            ]
            commands = conda_command + commands
            if self.project.config.hpc.conda_location:
                source_commnad = [
                    executor_utils.RemoteCommand(
                        command=f"source {self.project.config.hpc.conda_location}",
                        execute_with_mpi=False,
                    )
                ]
                commands = source_commnad + commands
        
        db_job = sapi._get_config()["db"].get_jobs(
            limit=1,
            site_name=site_name,
            job_name=job_name,
        )[0]

        j = job.Job(
            site=sapi.get_site(self.project.config.hpc.sitename),
            commands=commands,
            job_type="raydensity_plotting",
            job_description = description,
            job_info={},
            wall_time_in_seconds=wall_time,

        )

        s_job.Job(
            site=sapi.get_site(site_name=db_job.site.site_name),
            commands=self.project.multi_mesh.get_interp_commands(event, gradient),
            job_type=db_job.job_type,
            job_info=db_job.info,
            jobname=db_job.job_name,
            job_description=db_job.description,
            wall_time_in_seconds=db_job.wall_time_in_seconds,
            working_dir=pathlib.Path(db_job.working_directory),
            tmpdir_root=pathlib.Path(db_job.temp_directory_root)
            if db_job.temp_directory_root
            else None,
            rundir_root=pathlib.Path(db_job.run_directory_root)
            if db_job.run_directory_root
            else None,
            job_groups=[i.group_name for i in db_job.groups],
            initialize_on_site=False,
        )



    def get_sims_for_plotting_task(
        self,
        reference_model: str,
        model_to_smooth: str,
        smoothing_lengths: List[float],
        smoothing_parameters: List[str],
    ) -> List[sc.simulation.Diffusion]:
        """
        Writes diffusion models based on a reference model and smoothing
        lengths. Then ploads them to the remote cluster if they don't exist there
        yet.
        and returns a list of simulations that can then be submitted
        as usual.

        The model_to_smooth [a
        Returns a list of simulation objects

        :param reference_model: Mesh file with the velocities on which smoothing lengths are based.
        This file should be locally present.
        :type reference_model: str
        :param model_to_smooth: Mesh file with the fields that require smoothing
        This may either be a file that is currently located on the HPC already
        or a file that stills needs to be uploaded. If it is located
        on the remote already, please pass a path starts with: "Remote:"
        :type model_to_smooth: str
        :param smoothing_lengths: List of floats that specify the smoothing lengths
        :type smoothing_lengths: list
        :param smoothing_parameters: List of strings that specify which parameters need smoothing
        :type smoothing_parameters: list
        """
        #ref_model_name = ".".join(reference_model.split("/")[-1].split(".")[:-1])
        #freq = 1.0 / self.project.lasif_settings.min_period
        hpc_cluster = self.project.flow.hpc_cluster

        #self.project.paths

        if "REMOTE:" not in model_to_smooth:
            print(
                f"Uploading initial values from: {model_to_smooth} " f"for smoothing."
            )
            file_name = model_to_smooth.split("/")[-1]
            remote_file_path = self.project.remote_paths.diff_dir / file_name
            self.project.flow.safe_put(model_to_smooth, remote_file_path)
            model_to_smooth = f"REMOTE:{remote_file_path}"

        sims = []
        for param in smoothing_parameters:
            if param.startswith("V"):
                reference_velocity = param
            # If it is not some velocity, use P velocities
            elif not param.startswith("V"):
                if "VPV" in self.project.config.inversion.inversion_parameters:
                    reference_velocity = "VPV"
                elif "VP" in self.project.config.inversion.inversion_parameters:
                    reference_velocity = "VP"
                else:
                    raise NotImplementedError(
                        "Inversionson always expects" "to get models with at least VP"
                    )

            unique_id = (
                "_".join([str(i).replace(".", "") for i in smoothing_lengths])
                + "_"
                + str(self.project.lasif_settings.min_period)
            )

            fname = f"{unique_id}_diff_model_{ref_model_name}_{param}.h5"
            remote_diff_model = self.project.remote_paths.diff_dir / fname
            diff_model_path = self.project.paths.diff_model_dir / fname

            if not os.path.exists(diff_model_path):
                smooth = smoothing.AnisotropicModelDependent(
                    reference_frequency_in_hertz=freq,
                    smoothing_lengths_in_wavelengths=smoothing_lengths,
                    reference_model=reference_model,
                    reference_velocity=reference_velocity,
                )
                diff_model = smooth.get_diffusion_model(reference_model)
                diff_model.write_h5(diff_model_path)

            if not hpc_cluster.remote_exists(remote_diff_model):
                self.project.flow.safe_put(diff_model_path, remote_diff_model)

            sim = sc.simulation.Diffusion(mesh=diff_model_path)
            sim.domain.polynomial_order = self.project.tensor_order
            sim.physics.diffusion_equation.courant_number = 0.06

            sim.physics.diffusion_equation.initial_values.filename = model_to_smooth
            sim.physics.diffusion_equation.initial_values.format = "hdf5"
            sim.physics.diffusion_equation.initial_values.field = f"{param}"
            sim.physics.diffusion_equation.final_values.filename = f"{param}.h5"

            sim.domain.mesh.filename = f"REMOTE:{remote_diff_model}"
            sim.domain.model.filename = f"REMOTE:{remote_diff_model}"
            sim.domain.geometry.filename = f"REMOTE:{remote_diff_model}"
            sim.validate()

            # append sim to array
            sims.append(sim)

        return sims
"""