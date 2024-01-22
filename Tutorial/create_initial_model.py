from salvus.mesh import simple_mesh
import toml
from salvus.mesh.tools.transforms import interpolate_mesh_to_mesh
from salvus.namespace import UnstructuredMesh

one_d = True

# Load in min period from LASIF config, this drives the resolution of the mesh
with open('INVERSIONSON_PROJECT_130s/LASIF_PROJECT/lasif_config.toml', 'r') as file:
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

if one_d:
    # Save the mesh in the LASIF project
    mesh.write_h5('INVERSIONSON_PROJECT_130s/LASIF_PROJECT/MODELS/initial_model.h5')

else:
    mesh_load = UnstructuredMesh.from_h5('INVERSIONSON_PROJECT/OPTIMIZATION/MODELS/x_00025_Radius_57735.9056944908.h5')
    mesh_interp = interpolate_mesh_to_mesh(
        mesh_load, 
        mesh, 
        use_layers=True, 
        use_1d_vertical_coordinate=True, 
        fields_to_interpolate = ['VSV', "VSH","VPV","VPH","RHO"]
    )
    mesh_interp.write_h5('INVERSIONSON_PROJECT_130s/LASIF_PROJECT/MODELS/initial_model.h5')



