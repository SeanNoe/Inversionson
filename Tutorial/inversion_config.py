from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class MonitoringConfig:
    iterations_between_validation_checks: int = 1  # not used if zero
    validation_dataset: List[str] = field(default_factory=lambda: [
        'GCMT_event_GREECE_Mag_6.2_2003-8-14-5',
        'GCMT_event_GULF_OF_CALIFORNIA_Mag_6.6_2006-1-4-8',
        'GCMT_event_NORTHERN_MID-ATLANTIC_RIDGE_Mag_6.0_2013-9-5-4',
        'GCMT_event_MINDANAO_PHILIPPINES_Mag_6.4_2019-10-16-11',
        'GCMT_event_LOYALTY_ISLANDS_Mag_6.8_2011-5-10-8',
        'GCMT_event_QUEEN_CHARLOTTE_ISLANDS_REGION_Mag_6.0_2003-7-12-23',

    ])


@dataclass(frozen=True)
class MeshingConfig:
    # Use multi-mesh True or False
    multi_mesh: bool = True

    # The below is only relevant for SmoothieSEM meshes
    elements_per_azimuthal_quarter: int = 4
    elements_per_wavelength: float = 2.0
    ellipticity: bool = True

    # Ocean loading settings
    ocean_loading: bool = True
    ocean_loading_file: Path = Path("/home/sebastian/workflow_setup/bathy_and_topo/bathymetry_earth2014_lmax_10800.nc")
    ocean_loading_var_name: str = "bathymetry_earth2014_lmax_10800_lmax_16"

    # Topography settings
    topography: bool = True
    topography_file: Path = Path("/home/sebastian/workflow_setup/bathy_and_topo/topography_earth2014_egm2008_lmax_10800.nc")
    topography_var_name: str = "topography_earth2014_egm2008_lmax_10800_lmax_16"


@dataclass(frozen=True)
class HPCSettings:
    sitename: str = "daint"
    max_reposts: int = 1
    sleep_time_in_seconds: float = 30.0
    conda_env_name: str = "salvus"
    conda_location: Path = Path("~/miniconda3/etc/profile.d/conda.sh")
    inversionson_folder: Path = Path(
        "/scratch/snx3000/snoe/INVERSIONSON_PROJECT"
    )

    # Data processing
    data_proc_wall_time: float = 600.0
    remote_data_dir: Path = Path(
        "/project/s1238/snoe/GLOBAL_DATASET/EARTHQUAKES"
    )

    # Wave propagation settings
    n_wave_ranks: int = 60
    wave_wall_time: float = 400.0

    # Diffusion settings
    n_diff_ranks: int = 60
    diff_wall_time: float = 400.0

    # Interpolation settings
    grad_interp_wall_time: float = 360.0
    model_interp_wall_time: float = 360.0

    # Output Processing settings
    proc_wall_time: float = 260


@dataclass(frozen=True)
class InversionSettings:
    initial_model: Path = Path("/home/sebastian/workflow_setup/INVERSIONSON_PROJECT/LASIF_PROJECT/MODELS/initial_model.h5")
    mini_batch: bool = True  # Use mini-batches or not.
    initial_batch_size: int = 30
    source_cut_radius_in_km: float = 800.0
    speculative_adjoints: bool = True # When set to true, adjoint simulations are submitted before a model is accepted
    smoothing_lengths: List[float] = field(default_factory=lambda: [0.35, 0.7, 0.7])
    # Values between 0.55 - 1.0. The number represents the quantile where the gradient will be clipped. If 1.0 nothing will be clipped.
    clipping_percentile: float = 0.999
    # You specify the length of the absorbing boundaries in the lasif config
    absorbing_boundaries: bool = False
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
