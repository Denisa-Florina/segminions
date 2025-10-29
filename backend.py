from flask import Flask, render_template, request, send_file
import os
import pydicom
import numpy as np
import matplotlib.pyplot as plt
from ai_model import SegmentationModel

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

model = SegmentationModel()

def overlay_mask(image, mask, color=[1,0,0], alpha=0.4):
    result = np.stack([image, image, image], axis=-1)
    result[mask == 1] = [1, 0, 0]
    return result


@app.route("/", methods=["GET", "POST"])
def index():
    output_path = None
    metrics = None

    if request.method == "POST":
        file = request.files["dicom_file"]
        if file:
            # salvam img in fisierul ul uploads
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)

            # citim img dicom
            dicom_data = pydicom.dcmread(filepath) #librarie speciala care citeste fisierele dicom
            print(dicom_data)
            image = dicom_data.pixel_array.astype(float) #converteste img in float pentru normalizare/segmentare

            # procesam
            image_norm = model.preprocess(image)
            mask, metrics = model.predict(image_norm)
            result = overlay_mask(image_norm, mask, alpha=0.5)
           
            # salvam imaginea rezultată
            output_path = os.path.join("static", "output.png")
            plt.imsave(output_path, result, cmap="gray")

            #print(metrics)

    return render_template("index.html", output_path=output_path, metrics=metrics)

if __name__ == "__main__":
    app.run(debug=True)
