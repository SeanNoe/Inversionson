# Inversionson

**Inversionson** is a workflow manager which fully automates FWI workflows, optimizing for both computational- and human time.
In collaboration with [Salvus](https://mondaic.com), it makes working with a combination of local machines and HPC clusters easy.
Setting up a large-scale seismic inversion and running it has never been easier and more efficient.

There exists an [open-access paper about Inversionson](https://eartharxiv.org/repository/view/2132/). If you use Inversionson, please consider citing it:

```bibtex
@article{thrastarson2021inversionson,
  title={Inversionson: Fully Automated Seismic Waveform Inversions},
  author={Thrastarson, Solvi and van Herwaarden, Dirk-Philip and Fichtner, Andreas},
  year={2021},
  publisher={EarthArXiv},
  doi = {10.31223/X5F31V},
  url = {https://doi.org/10.31223/X5F31V}
}
```

The paper describes workflows which were supported in [v0.0.1](https://github.com/solvithrastar/Inversionson/releases/tag/v0.0.1-minibatch) of Inversionson.
In the latest version, we have made some changes.
In the previous version, we used optimization routines from Salvus, but we have now stopped supporting them and created a basis for implementing our own optimization routines within Inversionson.

Inversionson has built in support for using a validation dataset, which is a dataset that is not explicitly a part of the inversion but is reserved for monitoring the inversion procedure with an independent dataset.
The validation dataset can be used to tune regularization for example. There is also support for reserving a test dataset to compute misfit for at the end of the inversion process.

The design principle of Inversionson is that it runs on a machine that can in principle be a laptop, but ideally it's a desktop machine.
This machine only serves as a controller and does not do any heavy computations. It submits jobs to HPC clusters to do everything that would normally take time.
This is done in order to make the workflow as parallel as possible, and it saves a lot of time.

# Inversionson Setup and Installation

In the following, we set up the environment and all required packages for the global full-waveform inversion workflow on a remote machine. Make sure to first install either `conda` or `mamba`. The following commands are demonstrated with `mamba` as it is much faster compared to `conda`.

## Local machine

### Install Salvus
Detailed info in the documentation on www.mondaic.com.
```
# Python 3.9
curl https://mondaic.com/environment-py39.yml -o environment.yml

# Create a new environment with all required dependencies.
mamba env create -n salvus -f environment.yml

# Activate the environment
conda activate salvus
```

Run the mondaic downloader. Here, you need your software credentials. Autodetected default options are fine.

```
# Run the Mondaic downloader
bash -c "$(curl -sSL https://get.mondaic.com)"
```

```
pip install ~/Salvus/python_packages/salvus-*.whl

```

Now, Salvus can be imported in a python script. To run simulations, we need to set up the site. We set up two sites, one local and one remote. The local site is not needed for the workflow, however it is nice to have for small quick tests.

```
# Set up local site
salvus-cli add-site
# Choose 'local' and follow instructions
```

The setup for the remote site is a bit more involved. At the beginning choose remote, and follow the instructions. Make sure that you can access the remote site via ssh.

```
# Set up remote site
salvus-cli add-site
```

Recommended options. If information not given below, please select the default option.

`site-type: slurm`,<br>
`name: daint`,<br>
`Install Salvus`,<br>
`Run Downloader at remote site. Continue? y`,<br>
Give you software credentials
`default ranks: 12`,<br>
`max ranks: 1000`,<br>
The run and tmp directory of Salvus tend to get filled up quickly. Set them up on the scratch system.,<br>
`run_directory: /scratch/snx3000/USERNAME/salvus_flow/run_directory`,<br>
`tmp_directory: /scratch/snx3000/USERNAME/salvus_flow/tmp_directory`,<br>
`use_cuda_capable_gpus: y`,<br>
`tasks_per_node: 12`,<br>
`partition: normal`,<br>
`path_to_slurm_binaries: /usr/bin`<br>

There should be an entry called `daint` in <br>
`salvus-cli edit-config`

Some more configurations might be necessary. Below are my working settings for site `daint`. Change settings in `salvus-cli edit-config` to match the following. You may have to add/remove some lines.
```toml
[sites.daint]
        site_type = "slurm"
        default_ranks = 12
        max_ranks = 10000
        salvus_binary = "/users/USERNAME/Salvus/bin/salvus"
        run_directory = "/scratch/snx3000/USERNAME/salvus_flow/run"
        tmp_directory = "/scratch/snx3000/USERNAME/salvus_flow/tmp"
        use_cuda_capable_gpus = true
        [[sites.daint.environment_variable]]
            name = "CRAY_CUDA_MPS"
            value = "1"
        [[sites.daint.environment_variable]]
            name = "LD_LIBRARY_PATH"
            value = "/opt/cray/pe/mpt/7.7.15/gni/mpich-gnu-abi/8.2/lib"
        [sites.daint.ssh_settings]
            hostname = "daint"
            username = "snoe"
        [sites.daint.site_specific]
            tasks_per_node = 12
            partition = "normal"
            debug_partition = "debug"
            path_to_slurm_binaries = "/usr/bin"
            # Nov 2019: This is a workaround for a bug in the slurm version the
            # CSCS deployed. They are aware of it and are working on a fix.
            omit_default_srun_arguments = true
            # These are account/project dependent!
            [sites.daint.site_specific.additional_sbatch_arguments]
                name = "constraint"
                value = "gpu"
            [sites.daint.site_specific.additional_sbatch_arguments]
                name = "account"
                value = "s1238"
            [sites.daint.site_specific.modules_to_switch]
                old = "PrgEnv-cray"
                new = "PrgEnv-gnu"
            # Load an ABI compatible MPI module for Salvus to use.
            [sites.daint.site_specific.modules_to_switch]
                    old = "cray-mpich"
                    new = "cray-mpich-abi"

```

Run `salvus-cli init-site daint` to check if the site has been installed successfully. Optionally, do the same for the site `local`. If the sites have been successfully installed and initialized, we can move on.

### LASIF installation

LASIF is mostly an organization tool with some handy api functions for global or regional tomographic problems. It has data downloading options, processing functions, waveform vizualisation tools, and is able to compute gradients.

In the same environment, run
```
conda install numpy=1.24.3
git clone https://github.com/SeanNoe/LASIF_2.0.git
cd LASIF_2.0
git fetch
git checkout -t origin/dp/modify_source
pip install -e .
cd ..
```
(The numpy version needs to be fixed for the LASIF api. `umath_tests` causes problems otherwise. This may only be a temporary solution.)
### MultiMesh installation

This package manages the creation of event-adaptive meshes.

```
git clone https://github.com/SeanNoe/MultiMesh.git
cd MultiMesh
pip install -e .
cd ..
```
### Inversionson installation

This is the main package that we directly interact with. It is written as a wrapper around LASIF and fully automizes the entire workflow.

```
git clone https://github.com/SeanNoe/Inversionson.git
cd Inversionson
pip install -e .
cd ..
```

### Optson installation

Optson is a handy package to compute updates given a forward and gradient computation algorithm. It hosts the trust-region L-BFGS optimization algorithm and takes care of dynamic mini-batches.

```
git clone https://gitlab.com/swp_ethz/optson.git
cd optson
pip install -e .
cd ..
```

## On Remote daint

For some remote python scripts, like interpolations, data processing and window-picking, we need the proper environment and some packages on the remote machine.

### Salvus
Set up mamba and create salvus environment. Same as before:

```
# Python 3.9
curl https://mondaic.com/environment-py39.yml -o environment.yml

# Create a new environment with all required dependencies.
mamba env create -n salvus -f environment.yml

# Activate the environment
conda activate salvus
```

Salvus should already be installed here. Therefore, we can skip the download step and install it directly.

```
pip install ~/Salvus/python_packages/salvus-*.whl

```

There is no need to set up sites.

### LASIF

In the same environment, run 
```
git clone https://github.com/SeanNoe/LASIF_2.0.git
cd LASIF_2.0
git fetch
git checkout -t origin/dp/modify_source
pip install -e .
cd ..
```
### MultiMesh

```
git clone https://github.com/SeanNoe/MultiMesh.git
cd MultiMesh
pip install -e .
cd ..
```

### Inversionson

```
git clone https://github.com/SeanNoe/Inversionson.git
cd Inversionson
pip install -e .
cd ..
```

This should be it.


# Dummy Project

This is a little tutorial to set up a dummy problem. The dummy problem encompasses a long period global inversion on the full data set. Below, the configurations for Inversionson are described in detail. For reference, all the config-files and the script to create the simple starting model can be found in the `Tutorial`-folder. Just copy the files to their designated spot described below. 

During the steps, you will notice that the simulations themselves will run relatively fast to other tasts (pre-processing, post-processing, interpolations and smoothing).

### House keeping

Create the Inversionson-Project folder. This is where we store all intermediate results and from where we execute the inversion on a terminal.

```
mkdir INVERSIONSON_PROJECT
cd INVERSIONSON_PROJECT
lasif init_project LASIF_PROJECT
```

Get the data files from the remote machine. The full dataset is roughly 11 TB. Therefore, we only get the essential information to select Mini-Batches etc., while the receiver and waveform information is processed on the remote.

```
# Copy the empty earthquake files to the local machine
scp daint:'/project/s1238/snoe/empty_earthquakes/EARTHQUAKES/*.h5' LASIF_PROJECT/DATA/EARTHQUAKES/.
```

Bathymetry and Topography are vital for correct waveform simulations. Get a copy of the files from the remote. To deal here with high-resolved data, therefore the files are ~2 GB each. Strictly, for the tutorial, not the best resolution is needed, so feel free to download any of the other files in the remote folder. 

```
# Get a copy of the bathymetry and topography files
mkdir bathy_and_topo
scp daint:/project/s1238/snoe/bathy_and_topo/bathymetry_earth2014_lmax_10800.nc bathy_and_topo/.
scp daint:/project/s1238/snoe/bathy_and_topo/topography_earth2014_egm2008_lmax_10800.nc bathy_and_topo/.
```

### Adapt LASIF configuration

Configs to be adapted in the file `LASIF_PROJECT/lasif_config.toml`, everything else can be ignored.

```toml
# Adapt min and max periods
minimum_period_in_s = 160.0
maximum_period_in_s = 200.0
time_step_in_s = 0.1
end_time_in_s = 3600.0
start_time_in_s = -0.1
ocean_loading = true
domain_file = "/home/sebastian/workflow_setup/INVERSIONSON_PROJECT/LASIF_PROJECT/MODELS/initial_model.h5"
```

### Create starting velocity model
To get a simple starting model, run the following script. For the real setup, we would like to start from the final model (min period 33 s) from Solvi Thrastarson. Here, we initialize the dummy inversion with a 1D model.
```python
from salvus.mesh import simple_mesh
import toml


# Load in min period from LASIF config, this drives the resolution of the mesh
with open('LASIF_PROJECT/lasif_config.toml', 'r') as file:
    data = toml.load(file)

period = data['simulation_settings']['minimum_period_in_s']

print(f'Setting up mesh for a minimum period of {period} s.')

m = simple_mesh.Globe3D()
m.basic.min_period_in_seconds = period
m.basic.model = "prem_ani_one_crust"
m.advanced.tensor_order = 2
m.spherical.ellipticity = 0.0033528106647474805
m.basic.elements_per_wavelength = 2.0

mesh = m.create_mesh()

# Save the mesh in the LASIF project
mesh.write_h5('LASIF_PROJECT/MODELS/initial_model.h5')
```

Run THE MAGIC COMMAND of the automatic inversion tool: <br>
`python -m inversionson.autoinverter`

After the first execution, two config-files appear. We need to change a few things in these files.

### Adapt the inversion configuration

Open and adapt values in `inversion_config.py`.


#### Validation

Iterations between validation checks determines how often forward runs for the validation data set are submitted. This is vital for monitoring. Set to `iterations_betweens_validation_checks` to zero to not use a validation data set, however it is strongly recommended. 

Append a list of events. These events are designated for validation purposes only and will never be used for gradient computation. For the dummy inversion, we choose three events from the file list in `LASIF_PROJECT/DATA/EARTHQUAKES/`. In a serious application, the validation data set should be considerably larger.

```python
@dataclass(frozen=True)
class MonitoringConfig:
    iterations_between_validation_checks: int = 1  # not used if zero
    validation_dataset: List[str] = field(default_factory=lambda: [
        'GCMT_event_GREECE_Mag_6.2_2003-8-14-5',
        'GCMT_event_GULF_OF_CALIFORNIA_Mag_6.6_2006-1-4-8',
        'GCMT_event_NORTHERN_MID-ATLANTIC_RIDGE_Mag_6.0_2013-9-5-4',
        'GCMT_event_MINDANAO_PHILIPPINES_Mag_6.4_2019-10-16-11',
        'GCMT_event_LOYALTY_ISLANDS_Mag_6.8_2011-5-10-8',
        'GCMT_event_QUEEN_CHARLOTTE_ISLANDS_REGION_Mag_6.0_2003-7-12-23'
    ])

```

#### Meshing

The following designs the meshes. `multi_mesh = True` enables the use of event-adaptive meshes. Each event will have its own separate mesh for efficient computation. If `false`, all other configurations in `Meshingconfig`can be ignored.

The overall meshing density is driven by the minimum period (as defined in `LASIF_PROJECT/lasif_config.toml`) and `elements_per_wavelength`. Element-width in radial direction is driven by the two aforementioned factors. In azimuthal direction, we can ourselves define the density of the grid with the integer value in `elements_per_azimuthal_quarter`. Higher value means more accurate simulation with the tradeoff of being more expensive. For accurate simulations, `ellipticity` should always be true, and ocean-loading and topography files should be considered.

```python
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
```


#### HPC settings

Make sure that `sitename` corresponds to the name of the salvus site, that the site has been initialized with `salvus-cli init-site SITENAME` and that the remote can be reached with ssh (potentially protected with multifactor authentification). Occassionally, for no apparent reason, jobs tend to fail on the remote - `max_reposts` drives how many times a certain job is resubmitted before interrupting the whole workflow. `sleep_time_in_seconds` gives the ping-interval to check the status of submitted jobs.

`inversionson_folder` is where everything is stored on the remote location. Generally, everything in this folder can be deleted at any time - with the risk of having to re-compute some things. Should be on the `/scratch`-filesystem on daint.

The remote data repository holds the full waveform informations for all earthquakes. It has a size of ~11TB and therefore it saves a lot of time to keep it directly at the remote.

The rest defines wall-times for job types and the number of ranks.

```python
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
```

#### Inversion Settings

Here, we define the starting model created either by the script above or give a path to another model altogether. Set `mini_batch` to `True` to enable stochastic gradient computation. For our dummy example, a small `initial_batch_size` is fine. 

Setting `speculative_adjoints` to true will submit adjoint subs immediately after processing the forward results, even though the model might still be rejected. This speeds up the entire workflow with the risk of running a few empty simulations.

Regularization of the gradient is provided by a handful of parameters. To cut away effects from the source in the volumetric gradients, set`source_cut_radius_in_km`. `clipping_percentile` gets rid of extreme values in the gradient. The most important option here is `smoothing_lengths`. The provided list provides anisotropic smoothing lengths with respect to the wavelength. Vertical smoothing should be less than horizontal smoothing. Over the course of an inversion, smoothing lengths can be gradually reduced.

We keep default values in other parameters.

```python
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
```

### Adapt the optson configuration file

The file `optson_config.py` takes care of `Optson`, the package responsible for optimization. The default option is a trust-region L-BFGS optimization method, shown to be efficient for tomographic problems. The only parameter that may make sense to adapt is the `initial_step_size` for the first update. 5% seems to be a decent value. Even if the initial step length to too long, it will only result in some wasted forward computations at the start of the inversion until a model update is accepted.


```python
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
```

### Start the inversion

After everything is set up, all we need to do is to run this line again:

```terminal
python -m inversionson.autoinverter
```

That's it. The inversion can be interrupted and restarted at any time EXCEPT when something is up- or downloading. However, most of the time the iteration listener is checking in on jobs or waits until it pings the remote again, it is no problem to interrupt it then. When you want to change any inputs in the inversion configurations, interrupt the inversion, change the file, and restart the process with the magic command.


