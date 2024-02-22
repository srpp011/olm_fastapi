import os
import re
import json
import datetime

import pandas as pd
import glob
import requests
from typing import Union

from fastapi.openapi import models
from osgeo import gdal
import pyproj
from pyproj import Transformer, CRS,Geod
import numpy as np
from rasterio.enums import Resampling
from fastapi import FastAPI, Response, status, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Annotated
import models
from database import SessionLocal, engine
from sqlalchemy.orm import Session


DATA_DIR = '/code/data'
# populate_xlsx = r"C:\\Users\\srpp0\\PycharmProjects\\olm_fastapi\\LandGIS_tables.xlsx"
populate_xlsx = r"LandGIS_tables.xlsx"


app = FastAPI()
models.Base.metadata.create_all(bind=engine)

class LayerBase(BaseModel):
    request_url : str
    request_date : datetime.datetime
    name : str
    bbox : str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

# @app.post("/stats/")
# async def create_stats(layer: LayerBase, db: db_dependency):
#     db_layers = models.Layer(request_url=layer.request_url, name=layer.name, bbox=layer.bbox, request_date=datetime.datetime.now())
#     db.add(db_layers)
#     db.commit()
#     db.refresh(db_layers)

@app.get("/stats/")
async def get_stats(db: db_dependency):
    result = db.query(models.Layer).all()
    print(result)
    if not result:
        raise HTTPException(status_code=404, detail="Layer data not found")
    return result

@app.on_event("startup")
async def read_xls():
    global layers_data
    xls_data = pd.read_excel(populate_xlsx, sheet_name='landgis_layers', usecols="C,D,E,G,H,L,N,P,Q,R,S,T,U,W,X")
    # lyrs_data = xls_data.dropna(axis='columns')
    df1 = xls_data.astype(object).replace(np.nan, '')
    grouped_data = df1.groupby('layer_theme_new')
    layers_data = json.dumps(grouped_data.apply(lambda x: x.to_dict(orient='records')).to_dict())

def find_pixel_coordinates(raster, lon, lat, epsg):
    inProj = CRS("EPSG:4326")
    outProj = CRS(epsg)
    if inProj==outProj:
        x,y=lon,lat
    else:
        transformer = Transformer.from_crs(inProj, outProj, always_xy=True)
        x, y = transformer.transform(lon, lat)

    dataset = gdal.Open(raster)
    transform = dataset.GetGeoTransform()
    xOrigin = transform[0]
    yOrigin = transform[3]
    pixelWidth = transform[1]
    pixelHeight = transform[5]

    # Transformation of pixel coordinates
    x = int((x - xOrigin) / pixelWidth)
    y = int((y - yOrigin) / pixelHeight)

    return (x,y)

def read_pixel_on_multiple_images(file_list, lon, lat, epsg):
    values = []
    x, y = find_pixel_coordinates(file_list[0], lon, lat, epsg)

    for r in file_list:
        dataset = gdal.Open(r)
        band = dataset.GetRasterBand(1)

        value = band.ReadAsArray(xoff=x, yoff=y, win_xsize=1, win_ysize=1)[0, 0]
        filename = os.path.basename(r)

        # #Inverse mapping (reverse process) if the values are normalized! Some TIFFs are normalized.
        if band.GetScale() is not None and band.GetOffset() is not None:
            value = value * band.GetScale() + band.GetOffset()

        values.append({filename: float(value)})
    return values

@app.get("/")
def root_address():
    return "Openland map is running on FAST API backend."

@app.get("/populate")
async def populate():
    try:
        if len(layers_data)>0:
            return Response(content=layers_data, status_code=200)
    except:
        return JSONResponse({'error': 'Error while reading data from file.'}, status_code=400)

@app.get("/query/point")
async def point(db: db_dependency, lon: str, lat: str, coll: Union[str, None], regex: str, mosaic: bool = False, oem: bool = False):

    files = []

    if coll == "log.oc_iso.10694_m_1km_.*_.*_.*_go_espg.4326_v20230608":
        coll = "log_oc_iso"
    if coll == "no2_s5p_l3_trop_tmwm":
        coll = "no2_s5p_l3_trop_tmwm"
    if mosaic and not oem:
        root_dir = f"{DATA_DIR}/olm/layers/mosaics"
        generic_root_dir = "/code/data/s3/olm/arco"
        files = [f"{generic_root_dir}/{f.split('/')[-1]}" for f in glob.glob(f'{root_dir}/{coll}/{regex}')]
    if oem:
        root_dir = f"{DATA_DIR}/earthmonitor/layers"
        files = glob.glob(f'{root_dir}/{coll}/{regex}')
    if regex != '*.tif':
        root_dir = "/code/data/s3/olm/arco"
        if coll is None:
            regex = regex.replace('.*', '*')
            files = glob.glob(f'{root_dir}/{regex}')
        else:
            files = glob.glob(f'{root_dir}/{coll}/{regex}')

    if not files:
        return JSONResponse({'error': 'The corresponding files could not be found. Please verify coll or regex parameter.'}, status_code=400)

    try:
        lon = float(lon)
        lat = float(lat)
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError('Longitude must be between -180 and 180, and Latitude between -90 and 90!')
    except Exception as e:
        return JSONResponse({'error': 'Wrong latitude/longitude format - please provide both values as numbers (-180<= lon <=180 and -90<= lat <=90)'}, status_code=400)


    try:
        f = files[0]
        epsg = f.split('epsg.')[1].split('_')[0]
    except:
        epsg = 4326
    pq = read_pixel_on_multiple_images(files, lon, lat, epsg)

    # stats:
    try:
        lyr = files[0]
        point = f'POINT({lat} {lon})'
        db_layers = models.Layer(name=lyr, location=point, request_date=datetime.datetime.now())
        db.add(db_layers)
        db.commit()
        db.refresh(db_layers)
    except:
        pass


    # for data in pq:
    #     for filename, value in data.items():
    #         match = re.search(r'_(\d{8}_\d{8})_', filename)
    #         if match:
    #             date_param = match.group(1)
    #             extracted_item[f"{date_param[:8]}_{date_param[9:]}"] = value
    #         else:
    #             match = re.search(r'_(\d{4}_\d{4})_', filename)
    #             date_param = match.group(1)
    #             extracted_item[f"{date_param}"] = value
    return JSONResponse(pq, status_code=200)

@app.get("/rss-feed")
async def get_feed():
    try:

        url = "https://medium.com/feed/@opengeohub"

        payload = {}

        response = requests.request("GET", url, data=payload)

        data = response.text
        return Response(content=data, media_type="application/xml")

    except:
        return JSONResponse({'error': 'Error while reading data from file.'}, status_code=400)



# lat=59.42693461518746
# lon=13.421783447265616
# coll="lc_glc_fcs30d"
# regex="*.tif"

# lat=49.35914293941917
# lon=9.115142822265616
# coll='lc_mcd12q1v061_p1'
# regex='*.tif'

# lat=50.93595050607959
# lon=4.105377197265616
# coll="nightlights_500m"
# regex="*.tif"

# lat=57.4730366639736
# lon=29.242095947265614
# regex="lst_mod11a2.nighttime.trend.logit.ols.beta_m_1km_s_.*_go_epsg.4326_v1.2.tif"

# lat=43.90385186684824
# lon=-1.6075134277343825
# coll="log.oc_iso.10694_m_1km_.*_.*_.*_go_espg.4326_v20230608"
# regex="*.tif"