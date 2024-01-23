from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class MonitoringConfig:
    iterations_between_validation_checks: int = 2  # not used if zero
    validation_dataset: List[str] = field(default_factory=lambda: ['GCMT_event_AEGEAN_SEA_Mag_4.9_2017-2-16-0',
                        'GCMT_event_AZORES_ISLANDS_REGION_Mag_5.3_2010-8-13-5',
                                'GCMT_event_CENTRAL_ITALY_Mag_4.7_2016-8-25-12',
                                        'GCMT_event_DODECANESE_ISLANDS_GREECE_Mag_4.9_2008-7-15-23',
                                                'GCMT_event_GREECE-ALBANIA_BORDER_REGION_Mag_4.7_2019-6-1-18',
                                                        'GCMT_event_GREECE_Mag_5.2_2008-10-14-2',
                                                                'GCMT_event_ICELAND_REGION_Mag_5.2_2010-10-23-21',
                                                                        'GCMT_event_JAN_MAYEN_ISLAND_REGION_Mag_4.8_2012-11-1-6',
                                                                                'GCMT_event_JORDAN_-_SYRIA_REGION_Mag_5.1_2008-2-15-10',
                                                                                        'GCMT_event_NORTHERN_ALGERIA_Mag_4.9_2009-12-14-6',
                                                                                                'GCMT_event_NORTHERN_MID-ATLANTIC_RIDGE_Mag_4.8_2008-9-2-2',
                                                                                                        'GCMT_event_NORTHWESTERN_BALKAN_REGION_Mag_4.7_2012-7-27-23',
                                                                                                                'GCMT_event_NORWEGIAN_SEA_Mag_5.1_2015-6-2-7',
                                                                                                                        'GCMT_event_REYKJANES_RIDGE_Mag_5.1_2009-7-7-7',
                                                                                                                                'GCMT_event_SOUTHERN_ITALY_Mag_4.7_2018-8-14-21',
                                                                                                                                        'GCMT_event_SVALBARD_REGION_Mag_5.0_2010-7-30-9',
                                                                                                                                                'GCMT_event_TURKEY_Mag_5.1_2008-11-12-14'])


@dataclass(frozen=True)
class MeshingConfig:
    # Use multi-mesh True or False
    multi_mesh: bool = True  # For global-scale multi-mesh only leave the first flag on True
    multi_mesh_regional: bool = True  # For regional-scale projects set both to True

    # The below is only relevant for SmoothieSEM meshes
    elements_per_azimuthal_quarter: int = 6
    elements_per_wavelength: float = 2
    ellipticity: bool = True

    # Ocean loading settings
    ocean_loading: bool = True
    ocean_loading_file: Path = Path("/home/cjschiller/Documents/Inversionson/Tutorial/regional_dummy_project/bathy_and_topo/bathymetry_earth2014_lmax_10800.nc")
    ocean_loading_var_name: str = "bathymetry_earth2014_lmax_10800_lmax_16"

    # Topography settings
    topography: bool = True
    topography_file: Path = Path("/home/cjschiller/Documents/Inversionson/Tutorial/regional_dummy_project/bathy_and_topo/topography_earth2014_egm2008_lmax_10800.nc")
    topography_var_name: str = "topography_earth2014_egm2008_lmax_10800_lmax_16"

    # Refinement settings
    refinement: bool = True
    refinement_theta_min = 30.0
    refinement_theta_max = 160.0
    refinement_r_min = 6200.0
    # if needed refine again after first refinement; set flag to True
    double_refinement: bool = False 
    double_refinement_theta_min = 80.0
    double_refinement_theta_max = 160.0
    double_refinement_r_min = 6250.0

@dataclass(frozen=True)
class HPCSettings:
    sitename: str = "daint"
    max_reposts: int = 1
    sleep_time_in_seconds: float = 30.0
    conda_env_name: str = "lasif"
    conda_location: Path = Path("~/miniconda3/etc/profile.d/conda.sh")
    inversionson_folder: Path = Path(
        "/scratch/snx3000/cschille/INVERSIONSON_EU_Dummy"
    )

    # Data processing
    data_proc_wall_time: float = 600.0
    remote_data_dir: Path = Path(
        "/project/s1238/cschille/LASIF_EU_2.0_low_periods/DATA/EARTHQUAKES"
    )

    # Wave propagation settings
    # Rule of thumb: 1 Rank for every 3000 mesh elements in SEM
    n_wave_ranks: int = 60 
    wave_wall_time: float = 400.0

    # Diffusion settings
    n_diff_ranks: int = 60
    diff_wall_time: float = 400.0

    # Interpolation settings
    grad_interp_wall_time: float = 3600.0
    model_interp_wall_time: float = 3600.0

    # Output Processing settings
    proc_wall_time: float = 260

    # Time Step settings
    manual_time_step: bool = True
    # set time step in LASIF Folder

@dataclass(frozen=True)
class InversionSettings:
    initial_model: Path = Path("/home/cjschiller/Documents/Inversionson/Tutorial/regional_dummy_project/LASIF_EU_dummy.h5")
    mini_batch: bool = True  # Use mini-batches or not.
    initial_batch_size: int = 30 #depending on your event dataset size, mini-batches that are as big as about 30-40% of the max. available events is recommended.
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
