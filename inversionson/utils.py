from typing import List, Union, Tuple
import numpy as np
from pathlib import Path
import h5py  # type: ignore
from salvus.mesh.unstructured_mesh import UnstructuredMesh as UM
from optson.vector import Vec
import numpy as np
import hashlib

__FILE_TEMPLATES_DIR = Path(__file__).parent / "file_templates"


def write_xdmf(filename: Union[Path, str]) -> None:
    """
    Takes a path to an h5 file and writes the accompanying xdmf file.

    :param filename: Filename of the h5 file that needs an xdmf file.
    Should be a Path or str.
    """
    filename = Path(filename)

    xdmf_attribute_path = __FILE_TEMPLATES_DIR / "attribute.xdmf"
    base_xdmf_path = __FILE_TEMPLATES_DIR / "base_xdmf.xdmf"

    # Get relevant info from h5 file
    with h5py.File(filename, "r") as h5:
        num_big_elements = h5["MODEL"]["coordinates"].shape[0]
        nodes_per_element = h5["MODEL"]["coordinates"].shape[1]
        dimension = h5["MODEL"]["coordinates"].shape[2]
        total_points = num_big_elements * nodes_per_element
        tensor_order = round(nodes_per_element ** (1 / dimension) - 1)
        num_sub_elements = h5["TOPOLOGY"]["cells"].shape[0] * tensor_order**3

        dim_labels = h5["MODEL/data"].attrs.get("DIMENSION_LABELS")[1][1:-1]
        if type(dim_labels) != str:
            dim_labels = dim_labels.decode()
        dim_labels = dim_labels.replace(" ", "").split("|")

    # Write all atrributes
    with open(xdmf_attribute_path, "r") as fh:
        attribute_string = fh.read()
    all_attributes = ""

    final_filename = filename.name
    for i, attribute in enumerate(dim_labels):
        if i != 0:
            all_attributes += "\n"
        all_attributes += attribute_string.format(
            num_points=total_points,
            parameter=attribute,
            parameter_idx=i,
            num_elements=num_big_elements,
            nodes_per_element=nodes_per_element,
            num_parameters=len(dim_labels),
            filename=final_filename,
        )
    with open(base_xdmf_path, "r") as fh:
        base_string = fh.read().format(
            number_of_sub_elements=num_sub_elements,
            filename=final_filename,
            num_points=total_points,
            attributes=all_attributes,
        )

    xdmf_filename = ".".join(final_filename.split(".")[:-1]) + ".xdmf"
    complete_xdmf_filename = filename.parent / xdmf_filename

    with open(complete_xdmf_filename, "w") as fh:
        fh.write(base_string)


def get_window_filename(event: str, iteration: str) -> str:
    return f"{event}_{iteration}_windows.json"


def get_misfits_filename(event: str, iteration: str) -> str:
    return f"{event}_{iteration}_misfits.json"


def latlondepth_to_cartesian(
    lat: float, lon: float, depth_in_km: float = 0.0
) -> Tuple[float, float, float]:
    """
    Go from lat, lon, depth to cartesian coordinates

    :param lat: Latitude
    :type lat: float
    :param lon: Longitude
    :type lon: float
    :param depth_in_km: Depth in kilometers, Optional
    :type depth_in_km: float, defaults to 0.0
    :return: x,y,z coordinates
    :rtype: np.ndarray
    """
    R = (6371.0 - depth_in_km) * 1000.0
    lat *= np.pi / 180.0
    lon *= np.pi / 180.0
    x = R * np.cos(lat) * np.cos(lon)
    y = R * np.cos(lat) * np.sin(lon)
    z = R * np.sin(lat)

    return x, y, z


def get_tensor_order(filename: Union[str, Path]) -> int:
    """
    Get the tensor order from a Salvus h5 mesh file.
    """
    with h5py.File(filename, "r") as h5:
        num_gll = h5["MODEL"]["coordinates"].shape[1]
        dimension = h5["MODEL"]["coordinates"].shape[2]
    return int(round(num_gll ** (1 / dimension) - 1))


def get_h5_parameter_indices(
    filename: Union[str, Path], parameters: List[str]
) -> List[int]:
    """Get indices in h5 file for parameters in filename"""
    with h5py.File(filename, "r") as h5:
        h5_data = h5["MODEL/data"]
        dim_labels = h5_data.attrs.get("DIMENSION_LABELS")[1][1:-1]
        if type(dim_labels) != str:
            dim_labels = dim_labels.decode()
        dim_labels = dim_labels.replace(" ", "").split("|")
        indices = [dim_labels.index(param) for param in parameters]
    return indices

def get_elemental_parameter_indices(filename, parameters):
    """Get elemental parameter indices in h5 file"""
    with h5py.File(filename, "r") as h5:
        h5_data = h5["MODEL/element_data"]
        dim_labels = h5_data.attrs.get("DIMENSION_LABELS")[1][1:-1]
        if type(dim_labels) != str:
            dim_labels = dim_labels.decode()
        dim_labels = dim_labels.replace(" ", "").split("|")
        indices = [dim_labels.index(param) for param in parameters]
    return indices


def sum_two_parameters_h5(filename: Union[str, Path], parameters: List[str]):
    """sum two parameters in h5 file. Mostly used for summing VPV and VPH"""
    if not isinstance(filename, Path):
        filename = Path(filename)
    assert filename.exists(), "f{filename} does not exist. "
    assert len(set(parameters)) == 2, "Only implemented for two unique parameters."
    indices = get_h5_parameter_indices(filename, parameters)

    with h5py.File(filename, "r+") as h5:
        dat = h5["MODEL/data"]
        par_sum = dat[:, indices[0], :] + dat[:, indices[1], :]
        dat[:, indices[0], :] = par_sum
        dat[:, indices[1], :] = par_sum


def mesh_to_vector(m: Union[UM, str, Path], params_to_invert: List[str]) -> Vec:
    if isinstance(m, (str, Path)):
        m = UM.from_h5(m)
    layer_mask = np.where(m.elemental_fields["layer"] < 1.1, False, True).squeeze()
    par_list = [
        m.element_nodal_fields[param][layer_mask].flatten()
        for param in params_to_invert
    ]
    return np.concatenate(par_list)


def vector_to_mesh(x: Vec, target_mesh: UM, params_to_invert=List[str]) -> UM:
    par_vals = np.array_split(x, len(params_to_invert))
    m = target_mesh.copy()
    layer_mask = np.where(m.elemental_fields["layer"] < 1.1, False, True).squeeze()
    for idx, param in enumerate(params_to_invert):
        m.element_nodal_fields[param][layer_mask] = par_vals[idx].reshape(
            m.element_nodal_fields[param][layer_mask].shape
        )
    return m


def get_list_hash(lst: List[int]) -> str:
    """Compute a hash for a list of ints. Useful for identifying a set of
    samples."""
    sorted_lst = sorted(lst)
    lst_str = "".join(str(i) for i in sorted_lst)

    # Calculate the SHA-256 hash of the string representation
    hash_object = hashlib.sha256(lst_str.encode())
    return hash_object.hexdigest()[:7]


def hash_vector(vector: np.ndarray, max_sample_size: int = int(1e6)):
    """Get a hash for a vector. It's possible to only
    use a subset of the indices for very large vectors to save time."""
    # Fixing the seed for repeatability
    rng = np.random.RandomState(0)
    vector_length = len(vector)

    if vector_length > max_sample_size:
        indices = rng.randint(low=0, high=vector_length, size=max_sample_size)
        sample = vector[indices]
        sample_bytes = sample.tobytes()
    else:
        sample_bytes = vector.tobytes()

    hash_object = hashlib.sha256(sample_bytes)
    return hash_object.hexdigest()[:8]
