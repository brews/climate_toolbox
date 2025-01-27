"""
Handy functions for standardizing the format of climate data
"""

import xarray as xr
import numpy as np
import pandas as pd


def convert_kelvin_to_celsius(df, temp_name):
    """Convert Kelvin to Celsius"""
    df_attrs = df[temp_name].attrs
    df[temp_name] = df[temp_name] - 273.15
    # update attrs & unit information
    df[temp_name].attrs.update(df_attrs)
    df[temp_name].attrs["units"] = "C"
    df[temp_name].attrs["valid_min"] = -108.78788
    df[temp_name].attrs["valid_max"] = 62.02828

    return df


def convert_lons_mono(ds, lon_name="longitude"):
    """Convert longitude from -180-180 to 0-360"""
    ds[lon_name].values = np.where(
        ds[lon_name].values < 0, 360 + ds[lon_name].values, ds[lon_name].values
    )

    # sort the dataset by the new lon values
    ds = ds.sel(**{lon_name: np.sort(ds[lon_name].values)})

    return ds


def convert_lons_split(ds, lon_name="longitude"):
    """Convert longitude from 0-360 to -180-180"""
    ds[lon_name].values = xr.where(ds[lon_name] > 180, ds[lon_name] - 360, ds[lon_name])

    # sort the dataset by the new lon values
    ds = ds.sel(**{lon_name: np.sort(ds[lon_name].values)})

    return ds


def rename_coords_to_lon_and_lat(ds):
    """Rename Dataset spatial coord names to:
    lat, lon
    """
    if "latitude" in ds.coords:
        ds = ds.rename({"latitude": "lat"})
    if "longitude" in ds.coords:
        ds = ds.rename({"longitude": "lon"})
    elif "long" in ds.coords:
        ds = ds.rename({"long": "lon"})

    if "z" in ds.coords:
        ds = ds.drop("z").squeeze()

    return ds


def rename_coords_to_longitude_and_latitude(ds):
    """Rename Dataset spatial coord names to:
    latitude, longitude
    """
    if "lat" in ds.coords:
        ds = ds.rename({"lat": "latitude"})
    if "lon" in ds.coords:
        ds = ds.rename({"lon": "longitude"})
    elif "long" in ds.coords:
        ds = ds.rename({"long": "longitude"})

    if "z" in ds.coords:
        ds = ds.drop("z").squeeze()

    return ds


def remove_leap_days(ds):
    ds = ds.loc[{"time": ~((ds["time.month"] == 2) & (ds["time.day"] == 29))}]

    return ds


def season_boundaries(growing_days):
    """Returns the sorted start and end date of growing season"""

    # the longitude values of the data is off, we need to scale it
    growing_days.longitude.values = growing_days.longitude.values - 180
    # we then sort by longitude
    growing_days = growing_days.sortby("longitude")

    # construct the ds
    gdd_sorted = xr.DataArray(
        # xarray has no method to sort along an axis
        # we use np.sort but construct the matrix from a xarray dataArray
        # we use transpose to track the axis we want to sort along
        np.sort(
            growing_days.variable.transpose("latitude", "longitude", "z").values, axis=2
        ),
        dims=("latitude", "longitude", "sort"),
        coords={
            "latitude": growing_days.latitude,
            "longitude": growing_days.longitude,
            "sort": pd.Index(["min", "max"]),
        },
    )

    # we can then select an axis in the sorted dataarray as min
    min_day, max_day = gdd_sorted.sel(sort="min"), gdd_sorted.sel(sort="max")

    return min_day, max_day


def get_daily_growing_season_mask(lat, lon, time, growing_days_path):
    """

    Constructs a mask for days in the within calendar growing season

    Parameters
    ----------
    lat: xr.DataArray coords object
    lon: xr.DataArray coords object
    time: xr.DataArray coords object
    growing_days_path: str

    Returns
    -------
    DataArray
        xr.DataArray of masked lat x lon x time

    """

    growing_days = xr.open_dataset(growing_days_path)

    # find the min and max for the growing season
    min_day, max_day = season_boundaries(growing_days)

    data = np.ones((lat.shape[0], lon.shape[0], time.shape[0]))
    # create an array of ones in the shape of the data
    ones = xr.DataArray(data, coords=[lat, lon, time], dims=["lat", "lon", "time"])

    # mask the array around the within calendar year start and end times
    # of growing season
    mask = (ones["time.dayofyear"] >= min_day) & (ones["time.dayofyear"] <= max_day)

    # apply this mask and
    finalmask = (
        mask.where(growing_days.variable.sel(z=2) >= growing_days.variable.sel(z=1))
        .fillna(1 - mask)
        .where(~growing_days.variable.sel(z=1, drop=True).isnull())
        .rename({"latitude": "lat", "longitude": "lon"})
    )

    return finalmask
