from itertools import chain
from matplotlib import cm
import matplotlib.pyplot as plt
import numpy as np
from obspy.signal.tf_misfit import plot_tfr
from lasif.exceptions import LASIFError
import cmasher as cmr
from typing import Union, List, Dict 
import cartopy.crs as ccrs
from glob import glob
import pandas as pd
from matplotlib.ticker import FuncFormatter
from matplotlib.colors import LinearSegmentedColormap
import cartopy as cp
from geographiclib import geodesic
from matplotlib.collections import PathCollection
from matplotlib.legend_handler import HandlerPathCollection, HandlerLine2D
import glob
import warnings
import multiprocessing
import os
import pathlib
from tqdm import tqdm
import pyasdf
import sys
import toml

def update(handle, orig):
    handle.update_from(orig)
    handle.set_alpha(1)

def project_points(
    projection,
    lon: Union[np.ndarray, float],
    lat: Union[np.ndarray, float],
):
    """
    Define the correct projection function depending on name of projection
    """
    import pyproj
    import cartopy as cp

    proj_dict = projection.proj4_params
    event_loc = pyproj.Proj(proj_dict, preserve_units=True)
    x, y = event_loc(lon, lat)
    if isinstance(x, list):
        x = np.array(x)
        y = np.array(y)
    return x, y


def greatcircle_points_middle(
    point_1,
    point_2,
    max_extension=None,
    max_npts: int = 3000,
    start_fraction: float = 0.0,
    end_fraction: float = 1.0,
):
    """
    Generator yielding points along a greatcircle from point_1 to point_2.
    Modified to support partial segments of the great circle.
    
    :param point_1: Point 1 to draw the greatcircle between
    :param point_2: Point 2 to draw the greatcircle between
    :param max_extension: Fraction of max_npts to return
    :param max_npts: Maximum number of points to return
    :param start_fraction: Starting fraction along the path (0.0 to 1.0)
    :param end_fraction: Ending fraction along the path (0.0 to 1.0)
    """
    from lasif.utils import Point
    
    point = geodesic.Geodesic.WGS84.Inverse(
        lat1=point_1.lat, lon1=point_1.lng, lat2=point_2.lat, lon2=point_2.lng
    )
    line = geodesic.Geodesic.WGS84.Line(
        point_1.lat, point_1.lng, point["azi1"]
    )
    
    if max_extension:
        npts = int((point["a12"] / float(max_extension)) * max_npts)
    else:
        npts = max_npts - 1
    if npts == 0:
        npts = 1
    
    # Calculate which points to include based on fractions
    total_distance = point["s12"]
    start_distance = total_distance * start_fraction
    end_distance = total_distance * end_fraction
    
    # Generate points only in the specified range
    for i in range(npts + 1):
        current_distance = i * total_distance / float(npts)
        if start_distance <= current_distance <= end_distance:
            line_point = line.Position(current_distance)
            yield Point(line_point["lat2"], line_point["lon2"])


def plot_raydensity(
    map_object,
    station_events: list,
    projection,
    middle_fraction: float = 0.5,
):
    """
    Create a ray-density plot for all events and all stations, showing only the middle portion.
    
    :param map_object: The cartopy domain plot object
    :type map_object: cp.mpl.geoaxes.GeoAxes
    :param station_events: A list of tuples with two dictionaries
    :type station_events: List[Tuple[dict, dict]]
    :param projection: cartopy projection object
    :type projection: cp.crs.Projection
    :param middle_fraction: Fraction of the ray to keep (0.5 = middle 50%), default 0.5
    :type middle_fraction: float
    """
    import ctypes as C
    from lasif.tools.great_circle_binner import GreatCircleBinner
    from lasif.utils import Point
    import multiprocessing
    import progressbar
    from scipy.stats import scoreatpercentile
    import cartopy as cp

    # Merge everything so that a list with coordinate pairs is created
    station_event_list = []
    for event, station in station_events:
        e_point = Point(event["latitude"], event["longitude"])
        p = Point(station["latitude"], station["longitude"])
        station_event_list.append((e_point, p))

    circle_count = len(station_event_list)

    # The granularity of the latitude/longitude discretization
    if circle_count < 1000:
        lat_lng_count = 1000
    elif circle_count < 10000:
        lat_lng_count = 2000
    else:
        lat_lng_count = 3000

    cpu_count = multiprocessing.cpu_count()

    def to_numpy(raw_array, dtype, shape):
        data = np.frombuffer(raw_array.get_obj())
        data.dtype = dtype
        return data.reshape(shape)

    print(
        f"\nLaunching {circle_count} great circle calculations on {cpu_count} CPUs..."
        f"\n(Using middle {middle_fraction*100:.0f}% of each ray)"
    )

    widgets = [
        "Progress: ",
        progressbar.Percentage(),
        progressbar.Bar(),
        "",
        progressbar.ETA(),
    ]
    pbar = progressbar.ProgressBar(
        widgets=widgets, maxval=circle_count
    ).start()

    def great_circle_binning(
        sta_evs, bin_data_buffer, bin_data_shape, lock, counter, mid_frac
    ):
        """Modified to only bin the middle portion of each great circle"""
        new_bins = GreatCircleBinner(
            -89.,
            89.,
            lat_lng_count,
            -180.,
            180.,
            lat_lng_count,
        )
        
        # Calculate start and end fractions
        skip_fraction = (1.0 - mid_frac) / 2.0
        start_frac = skip_fraction
        end_frac = 1.0 - skip_fraction
        
        for event, station in sta_evs:
            with lock:
                counter.value += 1
            if not counter.value % 25:
                pbar.update(counter.value)
            
            # Add points only in the middle section
            for point in greatcircle_points_middle(
                event, station, new_bins.max_range, max_npts=3000,
                start_fraction=start_frac, end_fraction=end_frac
            ):
                new_bins.add_point(point)

        bin_data = to_numpy(bin_data_buffer, np.uint32, bin_data_shape)
        with bin_data_buffer.get_lock():
            bin_data += new_bins.bins

    # Split the data in cpu_count parts
    def chunk(seq, num):
        avg = len(seq) / float(num)
        out = []
        last = 0.0
        while last < len(seq):
            out.append(seq[int(last) : int(last + avg)])
            last += avg
        return out

    chunks = chunk(station_event_list, cpu_count)

    # One instance that collects everything
    collected_bins = GreatCircleBinner(
        -89.,
        89.,
        lat_lng_count,
        -180.,
        180.,
        lat_lng_count,
    )

    # Use a multiprocessing shared memory array
    collected_bins_data = multiprocessing.Array(
        C.c_uint32, collected_bins.bins.size
    )
    collected_bins.bins = to_numpy(
        collected_bins_data, np.uint32, collected_bins.bins.shape
    )

    # Create, launch and join one process per CPU
    processes = []
    lock = multiprocessing.Lock()
    counter = multiprocessing.Value("i", 0)
    for _i in range(cpu_count):
        processes.append(
            multiprocessing.Process(
                target=great_circle_binning,
                args=(
                    chunks[_i],
                    collected_bins_data,
                    collected_bins.bins.shape,
                    lock,
                    counter,
                    middle_fraction,
                ),
            )
        )
    for process in processes:
        process.start()
    for process in processes:
        process.join()

    pbar.finish()

    data = collected_bins.bins.transpose()

    if data.max() >= 10:
        data = np.log10(np.clip(data, a_min=0.5, a_max=data.max()))
        data[data >= 0.0] += 0.1
        data[data < 0.0] = 0.0
        max_val = scoreatpercentile(data.ravel(), 99.99)
    else:
        max_val = data.max()

    cmap = cm.get_cmap("gist_heat")
    cmap._init()
    cmap._lut[:120, -1] = np.linspace(0, 1.0, 120) ** 2

    lngs, lats = collected_bins.coordinates
    ln, la = project_points(projection, lngs, lats)
    
    def truncate_colormap(cmap, minval=0.0, maxval=1.0, n=100):
        """Truncate the colormap 'cmap' from minval to maxval."""
        new_cmap = LinearSegmentedColormap.from_list(
            'truncated_cmap', cmap(np.linspace(minval, maxval, n)))
        return new_cmap
    
    truncated_cmap = truncate_colormap(cmap, minval=0.0, maxval=0.9)

    p = map_object.pcolormesh(
        ln, la, data, cmap=truncated_cmap, vmin=0, vmax=max_val, zorder=10,
    )
    
    cbar = plt.colorbar(p, orientation='horizontal', pad=0.025, shrink=0.5)
    
    # Function to format ticks
    def log_formatter(x, pos):
        if 10**x > 10:
            return f"{int(round(10**x, -1))}"
        return f"{int(round(10**x, 0) - 1)}"

    # Set the formatter for the colorbar
    cbar.ax.xaxis.set_major_formatter(FuncFormatter(log_formatter))
    cbar.set_label(r'Rays per $0.1^\circ$ x $0.1^\circ$', fontsize=30)
    cbar.ax.tick_params(labelsize=20)
    
    return map_object, data


def plot_global_raydensity(station_and_events, save_path):
    sources = []
    receivers = []
    s_long = []
    s_lat = []
    r_long = []
    r_lat = []

    for station in station_and_events:
        sources.append((station[0]['longitude'], station[0]['latitude']))
        receivers.append((station[1]['longitude'], station[1]['latitude']))

    for tup in list(set(sources)):
        s_long.append(tup[0])
        s_lat.append(tup[1])

    for tup in list(set(receivers)):
        r_long.append(tup[0])
        r_lat.append(tup[1])

    fig = plt.figure(figsize=(30, 18))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Robinson(central_longitude=0))

    ax.scatter(s_long, s_lat, 700, c='yellow', marker='*', edgecolor='k', transform=ccrs.PlateCarree(), zorder = 12, label = "Events")
    ax.scatter(r_long, r_lat, 400, c = 'k', marker = 'v', alpha = 0.25,transform=ccrs.PlateCarree(), zorder = 11, label = "Receivers")        
    ax, data = plot_raydensity(ax, station_and_events, projection = ccrs.Robinson(central_longitude=0))
    ax.add_feature(cp.feature.COASTLINE, zorder = 13)
    #ax.add_feature(cp.feature.LAND, zorder = 1, edgecolor='k')
    ax.set_extent([-180, 180, -90, 90])
    ax.stock_img()

    ax.legend(loc = "lower right", fontsize = 30, bbox_to_anchor = (1, 1), handler_map={PathCollection : HandlerPathCollection(update_func= update),
                        plt.Line2D : HandlerLine2D(update_func = update)})

    plt.savefig(save_path,  bbox_inches='tight', dpi=1500)
    #plt.show()

def run(info):
    warnings.filterwarnings("ignore")
    num_processes = multiprocessing.cpu_count()

    global _collect_station_info

    proc_data_dir = info["REMOTE_PATHS"]["PROCESSED_DATA"]
    rayplots_dir = info["REMOTE_PATHS"]["RAYPLOTS"]
    iteration = info["REMOTE_PATHS"]["CURRENT_ITERATION"]

    proc_data_list = glob.glob(os.path.join(pathlib.Path(proc_data_dir), "*.h5"))
    plot_save_path = os.path.join(pathlib.Path(rayplots_dir), f"{iteration}_raydensity.png")

    def _collect_station_info(dataset):
        event_name = dataset.split("/")[-1][:-3]
        ds = pyasdf.ASDFDataSet(dataset, mode = "r", mpi=False)
        event = ds.events[0]
        station_events = {}
        for sta in ds.waveforms.list():
            try:
                station_events[sta] = ({'longitude':event.origins[0].longitude,
                                            'latitude':event.origins[0].latitude},
                                            {'longitude':ds.waveforms[sta].StationXML[0][0]._longitude,
                                            'latitude':ds.waveforms[sta].StationXML[0][0]._latitude})
            except:
                continue
        return {event_name: station_events} if station_events else {event_name: None}
    
    number_processes = min(num_processes, len(proc_data_list))

    print("Start collecting coordinates for Rayplot", flush=True)
    with multiprocessing.Pool(number_processes) as pool:
        station_and_events_dic = {}
        with tqdm(total=len(proc_data_list)) as pbar:
            for i, r in enumerate(pool.imap_unordered(_collect_station_info, proc_data_list)):
                pbar.update()
                k, v = r.popitem()
                station_and_events_dic[k] = v
        pool.close()
        pool.join()

    station_and_events = []

    for key1 in station_and_events_dic.keys():
        for key2 in station_and_events_dic[key1].keys():
            station_and_events.append(station_and_events_dic[key1][key2])
    
    plot_global_raydensity(station_and_events, plot_save_path)



if __name__ == "__main__":
    toml_filename = sys.argv[1]
    info = toml.load(toml_filename)
    run(info)