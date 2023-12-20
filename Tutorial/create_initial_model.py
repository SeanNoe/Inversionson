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