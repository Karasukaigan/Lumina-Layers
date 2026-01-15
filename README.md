# Lumina-Layers

[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Gradio](https://img.shields.io/badge/UI-Gradio-orange.svg)](https://gradio.app/)

**An experimental FDM engine exploring layered optical color mixing. The initial release features a specialized CMYK mode for converting pixel art into clean, artifact-free 3MF models.**

> 🚧 **Current Status**: This project is in its early experimental stage.
> * **Current Focus**: CMYK Pixel Art (Integer Geometry Optimization).
> * **Future Goal**: To support variable multi-filament systems (2, 4, 6, 8+ colors), complex photo dithering, and custom transmission distance (TD) profiling.

---

## ✨ Key Features (v1.0)

* **Pixel Art Optimized Geometry**:
    * Utilizes a specialized **Integer-based Slab Generation** algorithm.
    * Merges continuous pixels into solid bars along the X-axis.
    * **Solves the "internal wall overlapping" issue** common in voxel-based slicers, ensuring perfectly straight and clean toolpaths.
* **CMYK Optical Mixing**:
    * Simulates physical color blending based on **Transmission Distance (TD)**.
    * Calculates how Cyan, Magenta, Yellow, and White filaments layer to produce target colors.
* **Sandwich Structure**:
    * Automatically generates a **Face-Down + Spacer + Face-Up** structure.
    * Ideal for creating double-sided keychains or decorations with a light-blocking middle layer.
* **Smart Processing**:
    * **Auto Background Removal**: Detects and removes solid backgrounds.
    * **Pixel Perfect Scaling**: Forces Nearest-Neighbor resampling to maintain crisp pixel edges.

---

## 🛠️ Installation

1.  **Clone the repository**
    ```bash
    git clone [https://github.com/YourUsername/Lumina-Layers.git](https://github.com/YourUsername/Lumina-Layers.git)
    cd Lumina-Layers
    ```

2.  **Install dependencies**
    Ensure you have Python 3.8+ installed.
    ```bash
    pip install -r requirements.txt
    ```

---

## 🚀 Usage

1.  **Run the Engine**
    ```bash
    python app.py
    ```
    The GUI will open in your default web browser (usually `http://127.0.0.1:7860`).

2.  **Configuration Steps**
    * **Upload Image**: Drag and drop your pixel art image (PNG is recommended).
    * **Background Removal**: Enable "Auto Remove Background" if your image has a solid background color.
    * **TD Settings**: Input the **Transmission Distance** values for your specific filaments (values can be found via HueForge or filament manufacturer specs).
    * **Geometry**: Set the target width (mm) and spacer thickness.

3.  **Generate & Slice**
    * Click **"Generate"** to create the `.3mf` file.
    * Import the file into **Bambu Studio** (or other multi-color slicers).
    * **Important**: When importing, ensure you load it as a single object with multiple parts.
    * Map the filaments to the corresponding slots:
        * Index 0: **White**
        * Index 1: **Cyan**
        * Index 2: **Magenta**
        * Index 3: **Yellow**
        * Index 4: **Black** (Spacer)

---

## 🧩 Technical Insight

### The "Overlapping Path" Problem
Standard voxelization methods often generate thousands of individual cubes for pixel art. Slicers (like Bambu Studio) interpret these as separate objects, drawing perimeters around *every single pixel*. This results in chaotic toolpaths, over-extrusion, and extremely long print times.

### The Lumina-Layers Solution
Lumina-Layers uses an **Integer-Precision Slab Algorithm**. Instead of generating individual cubes:
1.  It scans the voxel matrix row by row.
2.  It identifies continuous segments of the same material.
3.  It constructs a single, solid rectangular mesh for that segment using integer coordinates.
4.  It applies a final matrix transformation to scale to physical dimensions.

This forces the slicer to recognize long, continuous regions, resulting in **monotonic linear infill** and a high-quality surface finish.

---

## 🗺️ Roadmap

* [x] **v1.0**: CMYK Pixel Art Mode (Solid Geometry Optimization)
* [ ] **v1.1**: Custom Filament Palettes (Support for non-CMYK sets)
* [ ] **v1.2**: Advanced Dithering for Photos/Illustrations
* [ ] **v2.0**: General Purpose Layering Engine (Variable layer heights)

---

## 📄 License

This project is licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**.

You are free to:
* **Share** — copy and redistribute the material in any medium or format.
* **Adapt** — remix, transform, and build upon the material.

Under the following terms:
* **Attribution** — You must give appropriate credit.
* **NonCommercial** — You may not use the material for commercial purposes.
* **ShareAlike** — If you remix, transform, or build upon the material, you must distribute your contributions under the same license as the original.

[View Full License](LICENSE)
