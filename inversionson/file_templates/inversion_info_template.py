from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class MonitoringConfig:
    iterations_between_validation_checks: int = 0  # not used if zero
    validation_dataset: List[str] = field(default_factory=lambda: [])


@dataclass(frozen=True)
class MeshingConfig:
    # Use multi-mesh True or False
    multi_mesh: bool = True  # For global-scale multi-mesh only leave the first flag on True
    multi_mesh_regional: bool = True  # For regional-scale projects set both to True

    # The below is only relevant for SmoothieSEM meshes
    elements_per_azimuthal_quarter: int = 4
    elements_per_wavelength: float = 2
    ellipticity: bool = True

    # Ocean loading settings
    ocean_loading: bool = False
    ocean_loading_file: Path = Path("/path/to/local/ocean_loading_file")
    ocean_loading_var_name: str = ""

    # Topography settings
    topography: bool = False
    topography_file: Path = Path("/path/to/local/topography_file")
    topography_var_name: str = ""

    # Refinement settings
    refinement: bool = True
    refinement_theta_min = 40.0
    refinement_theta_max = 160.0
    refinement_r_min = 6100.0
    # if needed refine again after first refinement; set flag to True
    double_refinement: bool = False 
    double_refinement_theta_min = 80.0
    double_refinement_theta_max = 160.0
    double_refinement_r_min = 6250.0

@dataclass(frozen=True)
class HPCSettings:
    sitename: str = "local"
    max_reposts: int = 3
    sleep_time_in_seconds: float = 30.0
    conda_env_name: str = "salvus"
    conda_location: Path = Path("~/miniconda3/etc/profile.d/conda.sh")
    inversionson_folder: Path = Path(
        "/scratch/snxXXXX/user/insert_project_name"
    )

    # Data processing
    data_proc_wall_time: float = 3600.0
    remote_data_dir: Path = Path(
        "/project/sXXXX/user/folder_with_lots_of_data"
    )

    # Wave propagation settings
    # Rule of thumb: 1 Rank for every 3000 mesh elements in SEM
    n_wave_ranks: int = 12 
    wave_wall_time: float = 3600.0

    # Diffusion settings
    n_diff_ranks: int = 12
    diff_wall_time: float = 3600.0

    # Interpolation settings
    grad_interp_wall_time: float = 3600.0
    model_interp_wall_time: float = 3600.0

    # Output Processing settings
    proc_wall_time: float = 3600

    # Time Step settings
    manual_time_step: bool = False
    # set time step in LASIF Folder

@dataclass(frozen=True)
class InversionSettings:
    initial_model: Path = Path("/user/some_starting_model.h5")
    mini_batch: bool = True  # Use mini-batches or not.
    initial_batch_size: int = 4 #depending on your event dataset size, mini-batches that are as big as about 30-40% of the max. available events is recommended.
    source_cut_radius_in_km: float = 100.0
    speculative_adjoints: bool = False # When set to true, adjoint simulations are submitted before a model is accepted
    smoothing_lengths: List[float] = field(default_factory=lambda: [0.5, 0.5, 0.5])
    # Values between 0.55 - 1.0. The number represents the quantile where the gradient will be clipped. If 1.0 nothing will be clipped.
    clipping_percentile: float = 1.0
    # You specify the length of the absorbing boundaries in the lasif config
    absorbing_boundaries: bool = True
    inversion_parameters: List[str] = field(
        default_factory=lambda: [
            "VPV",
            "VPH",
            "VSV",
            "VSH",
            "RHO",
        ]
    )
    modelling_parameters: List[str] = field(
        default_factory=lambda: [
            "VPV",
            "VPH",
            "VSV",
            "VSH",
            "RHO",
            "QKAPPA",
            "QMU",
            "ETA",
        ]
    )


class InversionsonConfig:
    def __init__(self):
        self.inversion_path: Path = Path(".")
        self.lasif_root: Path = Path("./LASIF_PROJECT")

        self.hpc = HPCSettings()
        self.inversion = InversionSettings()
        self.meshing = MeshingConfig()
        self.monitoring = MonitoringConfig()
