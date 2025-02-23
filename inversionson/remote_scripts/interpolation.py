import multi_mesh.api
import sys
import toml
import os
import shutil
import pathlib
import h5py
from inversionson.hpc_processing.utils import build_or_get_receiver_info
from inversionson.hpc_processing.cut_and_clip import (
    cut_source_region_from_gradient,
    clip_gradient,
)

# Here we should handle all the looking at the different mesh folders.
# If the mesh does not exist on scratch, we check on non-scratch.
# The from_mesh also needs to be found on either one of the two.
# This needs to be implemented on Monday/Saturday/Tuesday


def cut_and_clip(
    gradient_filename,
    source_location,
    parameters,
    radius_to_cut_in_km,
    clipping_percentile,
):
    """
    Cut and clip
    Needs the below keys in infp:
    gradient_filename = info["filename"]
    radius_to_cut_in_km = info["cutout_radius_in_km"]
    source_location = info["source_location"]
    clipping_percentile = info["clipping_percentile"]
    parameters = info["parameters"]
    """

    cut_source_region_from_gradient(
        gradient_filename,
        source_location,
        radius_to_cut=radius_to_cut_in_km,
        parameters=parameters,
    )

    print("Source cut completed successfully.")

    print("Clipping now.")
    if clipping_percentile < 1.0:
        clip_gradient(gradient_filename, clipping_percentile, parameters)

    # Set reference frame to spherical, This is done to inform the diffusion smoothing
    print("Set reference frame.")
    with h5py.File(gradient_filename, "r+") as f:
        attributes = f["MODEL"].attrs
        attributes.modify("reference_frame", b"spherical")


def process_data(processing_info):
    """
    Calls the processing function to process data that is stored on /project
    """

    from inversionson.hpc_processing.data_processing import preprocessing_function_asdf

    preprocessing_function_asdf(processing_info)


def create_mesh(mesh_info, source_info):
    mesh_location = mesh_info["event_specific_mesh"]

    if os.path.exists(mesh_location):
        print("Mesh already exists, copying it to here")
        shutil.copy(mesh_location, "./to_mesh.h5")
        return
    else:
        from salvus.mesh.simple_mesh import SmoothieSEM

        sm = SmoothieSEM()
        sm.basic.model = "prem_ani_one_crust"
        sm.basic.min_period_in_seconds = float(mesh_info["min_period"])
        sm.basic.elements_per_wavelength = float(mesh_info["elems_per_wavelength"])
        sm.basic.number_of_lateral_elements = int(mesh_info["elems_per_quarter"])
        sm.advanced.tensor_order = 4
        if "ellipticity" in mesh_info.keys():
            sm.spherical.ellipticity = float(mesh_info["ellipticity"])
        if "ocean_loading" in mesh_info.keys():
            sm.ocean.bathymetry_file = mesh_info["ocean_loading"]["remote_path"]
            sm.ocean.bathymetry_varname = mesh_info["ocean_loading"]["variable"]
            sm.ocean.ocean_layer_style = "loading"
            sm.ocean.ocean_layer_density = 1025.0
        if "topography" in mesh_info.keys():
            sm.topography.topography_file = mesh_info["topography"]["remote_path"]
            sm.topography.topography_varname = mesh_info["topography"]["variable"]
        sm.source.latitude = float(source_info["latitude"])
        sm.source.longitude = float(source_info["longitude"])
        sm.refinement.lateral_refinements.append(
            {"theta_min": 40.0, "theta_max": 140.0, "r_min": 6250.0}
        )
        m = sm.create_mesh()
        m.write_h5("to_mesh.h5", mode="all")


def get_standard_gradient(mesh_info):
    shutil.copy(mesh_info["master_gradient"], "./to_mesh.h5")


def move_mesh(mesh_path):
    mesh_location = pathlib.Path(mesh_path)
    if not os.path.exists(mesh_location):
        if not os.path.exists(mesh_location.parent):
            os.makedirs(mesh_location.parent)
        print("Copying mesh for storage")
        shutil.copy("./output/mesh.h5", mesh_location)


def interpolate_fields(from_mesh, to_mesh, layers, parameters, stored_array=None):
    multi_mesh.api.gll_2_gll_layered_multi_two(
        from_gll=from_mesh,
        to_gll=to_mesh,
        nelem_to_search=30,
        parameters=parameters,
        layers=layers,
        stored_array=stored_array,
        make_spherical=True,
    )


def move_nodal_field_to_gradient(mesh_info, field):
    """
    This is for moving a (z_node_1D) field from forward mesh to gradient
    """
    from salvus.mesh.unstructured_mesh import UnstructuredMesh as um

    mesh_location = mesh_info["event_specific_mesh"]

    m_for = um.from_h5(mesh_location)
    m_grad = um.from_h5("from_mesh.h5")
    m_grad.attach_field(field, m_for.element_nodal_fields[field])
    m_grad.write_h5("from_mesh.h5")
    print(f"Moved {field} to gradient")


def create_simulation_object(
    mesh_info, source_info, receiver_info, simulation_info, multi_mesh
):
    """
    Create the simulation object remotely and write it into a dictionary toml file.
    This dictionary is then downloaded and used locally to create the simulation object,
    bypassing the problem of slow receiver placements.

    The inputs are all dictionaries with the relevant information needed for
    the creation of the simulation object.
    """
    import salvus.flow.simple_config as sc

    receivers = [
        sc.receiver.seismology.SideSetPoint3D(
            latitude=rec["latitude"],
            longitude=rec["longitude"],
            network_code=rec["network-code"],
            station_code=rec["station-code"],
            depth_in_m=1.0,
            fields=["displacement"],
            side_set_name="r1",
        )
        for rec in receiver_info
    ]

    src = sc.source.seismology.SideSetMomentTensorPoint3D(
        latitude=source_info["latitude"],
        longitude=source_info["longitude"],
        depth_in_m=source_info["depth_in_m"],
        mrr=source_info["mrr"],
        mtt=source_info["mtt"],
        mpp=source_info["mpp"],
        mtp=source_info["mtp"],
        mrp=source_info["mrp"],
        mrt=source_info["mrt"],
        side_set_name=source_info["side_set"],
        source_time_function=sc.stf.Custom(
            filename=f"REMOTE:{source_info['stf']}", dataset_name="stf"
        ),
    )

    if multi_mesh:
        mesh = pathlib.Path().resolve() / "output" / "mesh.h5"
    else:
        mesh = pathlib.Path().resolve() / "from_mesh.h5"

    w = sc.simulation.Waveform(mesh=mesh, sources=src)
    w.add_receivers(receivers, max_iterations=100000)

    w.physics.wave_equation.end_time_in_seconds = simulation_info["end_time"]
    # We don't set the time step anymore
    # w.physics.wave_equation.time_step_in_seconds = simulation_info["time_step"]
    w.physics.wave_equation.start_time_in_seconds = simulation_info["start_time"]
    w.physics.wave_equation.attenuation = simulation_info["attenuation"]
    w.physics.wave_equation.courant_number = 0.45

    bound = False
    boundaries = []
    if simulation_info["absorbing_boundaries"]:
        print("I think there are absorbing boundaries")
        bound = True
        absorbing = sc.boundary.Absorbing(
            width_in_meters=simulation_info["absorbing_boundary_length"],
            side_sets=simulation_info["side_sets"],
            taper_amplitude=1.0 / simulation_info["minimum_period"],
        )
        boundaries.append(absorbing)

    if "ocean_loading" in mesh_info.keys():
        print("Applying ocean loading.")
        bound = True
        ocean_loading = sc.boundary.OceanLoading(side_sets=[source_info["side_set"]])
        boundaries.append(ocean_loading)
    if bound:
        w.physics.wave_equation.boundaries = boundaries

    # Compute wavefield and synthetics subsampling factor.
    if simulation_info["simulation_time_step"]:
        # Compute wavefield subsampling factor.
        samples_per_min_period = (
            simulation_info["minimum_period"] / simulation_info["simulation_time_step"]
        )
        min_samples_per_min_period = 40.0
        reduction_factor = int(samples_per_min_period / min_samples_per_min_period)
        reduction_factor_syn = int(samples_per_min_period / 40.0)
        # if reduction_factor_syn >= 2:
        #     w.output.point_data.sampling_interval_in_time_steps = reduction_factor_syn
        if reduction_factor >= 2:
            checkpointing_flag = f"auto-for-checkpointing_{reduction_factor}"
        else:
            checkpointing_flag = "auto-for-checkpointing"
    else:
        checkpointing_flag = "auto-for-checkpointing_5"

    w.output.volume_data.format = "hdf5"
    w.output.volume_data.filename = "output.h5"
    w.output.volume_data.fields = ["adjoint-checkpoint"]
    w.output.volume_data.sampling_interval_in_time_steps = checkpointing_flag
    w.validate()

    with open("output/simulation_dict.toml", "w") as fh:
        toml.dump(w.get_dictionary(), fh)


if __name__ == "__main__":
    """
    Call with python name_of_script toml_filename
    """
    toml_filename = sys.argv[1]

    info = toml.load(toml_filename)
    mesh_info = info["mesh_info"]

    # Process data if it doesn't exist already
    if info["data_processing"]:
        processing_info = info["processing_info"]
        if not os.path.exists(processing_info["asdf_output_filename"]):
            process_data(processing_info)

    if not info["gradient"]:
        if info["data_processing"]:
            asdf_file_path = processing_info["asdf_output_filename"]
            receiver_json_file = info["receiver_json_path"]
            receiver_info = build_or_get_receiver_info(
                receiver_json_file, asdf_file_path
            )
        else:
            receiver_info = info["receiver_info"]

        simulation_info = info["simulation_info"]
        source_info = info["source_info"]
        if info["multi-mesh"]:
            create_mesh(mesh_info=mesh_info, source_info=source_info)
            print("Mesh created or already existed")
    elif info["multi-mesh"]:
        get_standard_gradient(mesh_info=mesh_info)
        move_nodal_field_to_gradient(mesh_info=mesh_info, field="z_node_1D")

    if not os.path.exists(mesh_info["interpolation_weights"]):
        os.makedirs(mesh_info["interpolation_weights"])

    if info["multi-mesh"]:
        interpolate_fields(
            from_mesh="./from_mesh.h5",
            to_mesh="./to_mesh.h5",
            layers="nocore",
            parameters=["VPV", "VPH", "VSV", "VSH", "RHO"],
            stored_array=mesh_info["interpolation_weights"],
        )
        print("Fields interpolated")

    # Also clip the gradient here. We prefer not to use the login node anymore
    # for this if we have a job anyway.
    if info["gradient"]:
        cut_and_clip(
            "./to_mesh.h5",
            info["source_location"],
            info["parameters"],
            info["cutout_radius_in_km"],
            info["clipping_percentile"],
        )
    if info["multi-mesh"]:
        shutil.move("./to_mesh.h5", "./output/mesh.h5")
    if not info["gradient"]:
        if info["multi-mesh"]:
            move_mesh(mesh_info["event_specific_mesh"])
            print("Meshed moved to longer term storage")
        if info["create_simulation_dict"]:
            print("Creating simulation object")
            create_simulation_object(
                mesh_info,
                source_info,
                receiver_info,
                simulation_info,
                info["multi-mesh"],
            )
