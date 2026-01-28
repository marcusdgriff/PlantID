# PlantID Label Designer 

## Description
PlantID Label Designer is a Streamlit web application for generating customizable plant sample labels. The app allows researchers to visualize, design, and export labels with QR codes, highlighted metadata, and flexible sizing for a variety of use cases including cryovials, plant tags, wrap tags, and more.
It is designed to work both locally and on Streamlit Cloud.

## Try the online version
Try the app directly without installation
https://plantid-label-designer.streamlit.app

## Installation (Local)
Clone this repository
```bash
git clone https://github.com/marcusdgriff/PlantID.git
cd PlantID/PlantID-LabelDesigner-streamlit
```
Install required packages
```bash
pip install -r requirements.txt
```

## Running the app
Run the app locally:
```bash
streamlit run streamlit_app.py
```
Upload a CSV with your plant metadata. Configure label settings. Download the PDF for printing.
