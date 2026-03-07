# Install streamlit if not already installed
try:
    import streamlit
except ImportError:
    print("Streamlit not found. Installing now...")
   

# Install earthengine-api if not already installed
try:
    import ee
except ImportError:
    print("Earth Engine API not found. Installing now...")
  
import ee

import geemap.foliumap as geemap
import numpy as np
import streamlit as st
import folium.plugins # Import folium.plugins for drawing tools

# Authenticate and Initialize Earth Engine
ee.Authenticate()
ee.Initialize(project='pdr-jnu')

st.title("Potential Denitrification Rate (PDR) Estimation Web App")
st.write("Draw a region on the map to select an area and compute PDR.") # Updated instruction

# Create interactive map, disabling geemap's internal EE initialization
m = geemap.Map(center=[0, 0], zoom=3, ee_initialize=False)
m.add_basemap("SATELLITE")

# Add drawing tool to the map
draw_control = folium.plugins.Draw(export=False,
                    filename='data.geojson',
                    position='topleft',
                    draw_options={'polyline': False,
                                  'rectangle': True, # Allow drawing rectangles
                                  'circle': False,
                                  'marker': False,
                                  'circlemarker': False,
                                  'polygon': True # Allow drawing polygons
                                 })
m.add_child(draw_control) # Add as a child for better control

# Render the map and capture drawing results
# The `output` from to_streamlit() is expected to contain drawing data as a dict
output = m.to_streamlit(height=600)

roi = None
# Check if output is a dictionary and contains drawing data directly
if isinstance(output, dict) and output.get("last_active_drawing"):
    last_drawing = output["last_active_drawing"]
    geo_json_geometry = last_drawing.get("geometry")

    if geo_json_geometry:
        if geo_json_geometry.get("type") == "Polygon" or geo_json_geometry.get("type") == "Rectangle":
            roi = ee.Geometry.Polygon(geo_json_geometry['coordinates'])
        elif geo_json_geometry.get("type") == "Point":
            point_coords = geo_json_geometry['coordinates']
            roi = ee.Geometry.Point(point_coords).buffer(500) # 500 m buffer

# Fallback: if ROI wasn't set from direct output, try st.session_state
# This is a more robust way to handle Streamlit component state.
if not roi:
    if "last_active_drawing" in st.session_state and st.session_state["last_active_drawing"]:
        last_drawing_ss = st.session_state["last_active_drawing"]
        geo_json_geometry_ss = last_drawing_ss.get("geometry")
        if geo_json_geometry_ss:
             if geo_json_geometry_ss.get("type") == "Polygon" or geo_json_geometry_ss.get("type") == "Rectangle":
                roi = ee.Geometry.Polygon(geo_json_geometry_ss['coordinates'])
             elif geo_json_geometry_ss.get("type") == "Point":
                point_coords_ss = geo_json_geometry_ss['coordinates']
                roi = ee.Geometry.Point(point_coords_ss).buffer(500) # 500 m buffer


if roi:
    # Original logic to process data based on the selected ROI
    # Sentinel-2 image
    s2 = (ee.ImageCollection("COPERNICUS/S2_SR")
          .filterBounds(roi)
          .filterDate("2023-01-01", "2024-01-01") # Changed date to a recent period for available data
          .sort("CLOUDY_PIXEL_PERCENTAGE")
          .first())

    if s2: # Ensure an image was found before proceeding
        ndvi = s2.normalizedDifference(["B8", "B4"]).rename("NDVI")
        b11 = s2.select("B11")
        lulc = ee.Image("ESA/WorldCover/v200/2021").rename("LULC")

        # Combine layers, clipping them to the ROI
        data = ee.Image.cat([ndvi.clip(roi), b11.clip(roi), lulc.clip(roi)])

        # Example PDR model (placeholder formula)
        pdr = ndvi.multiply(0.6).add(b11.multiply(0.3)).add(lulc.multiply(0.1)).rename("PDR")

        # Display layers
        vis = {'min': 0, 'max': 1, 'palette': ['blue', 'green', 'yellow', 'red']}
        m.addLayer(pdr, vis, "PDR")
        m.addLayer(ndvi, {'min':0,'max':1,'palette':['white','green']}, "NDVI")
        m.addLayer(b11, {'min':0,'max':4000,'palette':['blue','white','brown']}, "B11")
        m.addLayer(lulc.randomVisualizer(), {}, "LULC")

        # Export button
        url = pdr.getDownloadURL({
            'scale': 30,
            'crs': 'EPSG:4326',
            'region': roi
        })
        st.markdown(f"[Download PDR GeoTIFF]({url})")
    else:
        st.warning("No Sentinel-2 image found for the drawn region within the specified date range. Please try drawing a different area or adjusting the date range.")
else:
    st.info("Please draw a region (rectangle or polygon) or click a point on the map to compute PDR.") # Instruction if no ROI is drawn yet
