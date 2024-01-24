import numpy as np
from salvus.mesh import simple_mesh
from salvus.mesh.mask_generators import SurfaceMaskGenerator
import lasif
import toml


# Load in min period from LASIF config, this drives the resolution of the mesh
with open('LASIF_PROJECT/lasif_config.toml', 'r') as file:
    data = toml.load(file)

period = data['simulation_settings']['minimum_period_in_s']

print(f'Summing up event-receiver locations')

comm = lasif.api.find_project_comm('LASIF_PROJECT/')
events = comm.events.list()

sources = []
for ev in events:
    event = comm.events.get(ev)
    sources.append((events['latitude'], events['longitude']))

print(f'Setting up mesh for a minimum period of {period} s.')

m = simple_mesh.Globe3D()
m.basic.min_period_in_seconds = period
m.basic.model = "prem_ani_one_crust"
m.advanced.tensor_order = 2
m.spherical.ellipticity = 0.0033528106647474805
m.basic.elements_per_wavelength = 2.0
m.spherical.min_radius = 37000
m.attenuation.number_of_linear_solids = 5

smg = SurfaceMaskGenerator(
    np.array(sources),
    number_of_points = 10000,
    distance_in_km = 2000,
)

mesh = m.create_mesh(mesh_processing_callback = smg)

print(f'Mesh has {mesh.nelem} number of elements')

# Save the mesh in the LASIF project
mesh.write_h5('LASIF_PROJECT/MODELS/initial_model.h5')