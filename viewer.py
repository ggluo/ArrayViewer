#!/usr/bin/env python3
# this simple array-viewer is generated by chatgpt and works after slight modifications

import tkinter as tk
from tkinter import ttk
import numpy as np
import matplotlib.pyplot as plt
plt.switch_backend('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sys
import logging
import multiprocessing

# Configure logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

def read_array_file(name):
    """
    Read a .cfl or .npy file and return the data as a NumPy array.
    """
    try:
        if name.endswith('.npy'):
            array = np.load(name)
            dims = list(array.shape)

        elif name.endswith(''):
            # get dims from .hdr
            with open(name + ".hdr", "r") as h:
                h.readline()  # skip
                l = h.readline()
            dims = [int(i) for i in l.split()]

            # remove singleton dimensions from the end
            n = np.prod(dims)
            dims_prod = np.cumprod(dims)
            dims = dims[:np.searchsorted(dims_prod, n) + 1]

            # load data and reshape into dims
            with open(name + ".cfl", "r") as d:
                a = np.fromfile(d, dtype=np.complex64, count=n)
            array = a.reshape(dims, order='F')
        else:
            raise ValueError("Unsupported file format. Only .cfl and .npy files are supported.")
        # Append dimensions to ensure the array has 12 dimensions
        while len(dims) < 12:
            dims.append(1)
        return array.reshape(dims)
        
    except Exception as e:
        raise ValueError(f"Error reading file: {e}")

class ArrayViewer:
    def __init__(self, root, array):
        self.root = root
        self.array = array
        self.array_shape = array.shape
        self.current_indices = [0] * 12  # Initialize indices for the 12 dimensions
        self.enabled_dims = [False] * 12  # Initialize enabled status for the 12 dimensions
        self.rotation_angle = 0  # Initialize rotation angle
        self.mirror = False  # Initialize mirroring
        self.colormap = 'gray'  # Initialize colormap
        self.display_mode = 'magnitude'  # Initialize display mode
        self.window_level = 0.5  # Initialize window level
        self.window_width = 1.0  # Initialize window width
        self.normalize_slice = False  # Initialize slice normalization

        
        main_frame = ttk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.controls_frame = ttk.Frame(main_frame)
        self.controls_frame.pack(side=tk.LEFT)
        
        self.index_vars = []
        self.check_vars = []

        non_singleton_dims = [i for i, dim in enumerate(array.shape) if dim > 1]

        if len(non_singleton_dims) >= 2:
            self.enabled_dims[non_singleton_dims[0]] = True
            self.enabled_dims[non_singleton_dims[1]] = True

        for i in range(12):
            
            check_var = tk.BooleanVar(value=self.enabled_dims[i])
            self.check_vars.append(check_var)
            
            combined_frame = ttk.Frame(self.controls_frame)
            combined_frame.grid(row=i, column=0, columnspan=1, pady=5)
            
            check = ttk.Checkbutton(combined_frame, style="Small.TCheckbutton", variable=check_var, command=self.update_view, width=2)
            check.pack(side=tk.LEFT)
            label = ttk.Label(combined_frame, text=f"Dim {i}:")
            label.pack(side=tk.LEFT)
             
            var = tk.IntVar(value=0)
            self.index_vars.append(var)
            
            spinbox = ttk.Spinbox(self.controls_frame, from_=0, to=array.shape[i] - 1, textvariable=var, command=self.update_view, width=5)
            spinbox.grid(row=i, column=2, columnspan=1)
            spinbox.bind('<MouseWheel>', lambda event, s=spinbox, v=var: self.on_spinbox_scroll(event, s, v))
            spinbox.bind('<Button-4>', lambda event, s=spinbox, v=var: self.on_spinbox_scroll(event, s, v))
            spinbox.bind('<Button-5>', lambda event, s=spinbox, v=var: self.on_spinbox_scroll(event, s, v))
            spinbox.bind('<FocusOut>', lambda event, s=spinbox, v=var: self.update_index(event, s, v, i))

            label1 = ttk.Label(self.controls_frame, text=f"{self.array_shape[i]}")
            label1.grid(row=i, column=3, columnspan=1, padx=5, pady=5)

            label1 = ttk.Label(self.controls_frame, text=f"{self.array_shape[i]}")
            label1.grid(row=i, column=3, columnspan=1, padx=5, pady=5)

        # Add buttons for rotation and mirroring
        rotation_frame = ttk.Frame(self.controls_frame)
        rotation_frame.grid(row=13, column=0, columnspan=5, pady=10)

        rotate_left_button = ttk.Button(rotation_frame, text="Rot L", command=self.rotate_left, width=5)
        rotate_left_button.pack(side=tk.LEFT, padx=2)

        rotate_right_button = ttk.Button(rotation_frame, text="Rot R", command=self.rotate_right, width=5)
        rotate_right_button.pack(side=tk.LEFT, padx=2)

        mirror_button = ttk.Button(rotation_frame, text="Mirror", command=self.mirror_image, width=5)
        mirror_button.pack(side=tk.LEFT, padx=2)

        # Add toggle button for magnitude/phase
        self.toggle_button = ttk.Button(rotation_frame, text="Mag", command=self.toggle_display_mode, width=5)
        self.toggle_button.pack(side=tk.LEFT, padx=2)

        save_button = ttk.Button(rotation_frame, text="Save", command=self.save_image, width=5)
        save_button.pack(side=tk.LEFT, padx=2)
        
        # Add window level and width controls
        window_frame = ttk.Frame(self.controls_frame)
        window_frame.grid(row=14, column=0, columnspan=5, pady=10)

        level_label = ttk.Label(window_frame, text="Level:")
        level_label.pack(side=tk.LEFT, padx=2)
        self.level_var = tk.DoubleVar(value=self.window_level)
        level_slider = ttk.Scale(window_frame, from_=0.0, to=1.0, variable=self.level_var, orient=tk.HORIZONTAL, command=self.update_window)
        level_slider.pack(side=tk.LEFT, padx=2)

        width_label = ttk.Label(window_frame, text="Width:")
        width_label.pack(side=tk.LEFT, padx=2)
        self.width_var = tk.DoubleVar(value=self.window_width)
        width_slider = ttk.Scale(window_frame, from_=0.1, to=2.0, variable=self.width_var, orient=tk.HORIZONTAL, command=self.update_window)
        width_slider.pack(side=tk.LEFT, padx=2)

        #  Add colormap selection and normalization toggle
        colormap_frame = ttk.Frame(self.controls_frame)
        colormap_frame.grid(row=15, column=0, columnspan=5, pady=10)

        colormap_label = ttk.Label(colormap_frame, text="Colormap:")
        colormap_label.pack(side=tk.LEFT, padx=2)
        
        self.colormap_var = tk.StringVar(value=self.colormap)
        colormap_combobox = ttk.Combobox(colormap_frame, textvariable=self.colormap_var, values=plt.colormaps(), width=10)
        colormap_combobox.pack(side=tk.LEFT, padx=2)
        colormap_combobox.bind("<<ComboboxSelected>>", self.update_colormap)

        normalize_check = ttk.Button(colormap_frame, text="Normalize", command=self.toggle_normalization, width=10)
        normalize_check.pack(side=tk.LEFT, padx=2)

        # Information display
        self.info_label = ttk.Label(self.controls_frame, text="", anchor="w", justify=tk.LEFT)
        self.info_label.grid(row=16, column=0, columnspan=5, sticky="w", pady=10)

        self.figure, self.ax = plt.subplots(1, 1, figsize=(10, 10))
        self.canvas = FigureCanvasTkAgg(self.figure, master=main_frame)
        self.canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.update_view()

    def get_current_slice(self):
        try:
            slices = []
            enabled_indices = [i for i, enabled in enumerate(self.check_vars) if enabled.get()]
            
            if len(enabled_indices) != 2:
                return None  # Only proceed if exactly two dimensions are enabled
            
            for i in range(12):
                if self.check_vars[i].get():
                    slices.append(slice(None))  # Keep this dimension as a slice
                else:
                    slices.append(self.index_vars[i].get())  # Fix this dimension at its current index
                    
            logging.debug(f"Current slices: {slices}")
            return self.array[tuple(slices)]
        except Exception as e:
            logging.error(f"Error in get_current_slice: {e}")
            return None

    def update_view(self, event=None):
        try:
            self.ax.clear()
            current_slice = self.get_current_slice()
            if current_slice is not None and current_slice.ndim == 2:
                if self.display_mode == 'magnitude':
                    image = np.abs(current_slice)
                else:
                    image = np.angle(current_slice)

                if self.normalize_slice:
                    image = (image - np.min(image)) / (np.max(image) - np.min(image))
                
                # Apply window level and width
                level = self.window_level
                width = self.window_width
                image = np.clip(image, level - width / 2, level + width / 2)
                image = (image - (level - width / 2)) / width
                
                # Apply rotation
                if self.rotation_angle != 0:
                    image = np.rot90(image, self.rotation_angle // 90)
                
                # Apply mirroring
                if self.mirror:
                    image = np.fliplr(image)
                
                self.ax.imshow(image, cmap=self.colormap, vmin=0, vmax=1)
                self.ax.axis('off')
                self.figure.tight_layout()
            else:
                self.ax.text(0.5, 0.5, 'Select exactly 2 dimensions to display', horizontalalignment='center', verticalalignment='center')
                self.ax.axis('off')
                self.figure.tight_layout()
            self.canvas.draw()

             # Update information display
            info_text = (
                f"Display: {self.display_mode}, Colormap: {self.colormap}\n"
                f"Normalization: {self.normalize_slice}, Max: {np.max(image):.2f}, Min: {np.min(image):.2f}\n"
                f"Level: {self.window_level:.2f}, Width: {self.window_width:.2f}\n"
                f"Rotation Angle: {self.rotation_angle}, Mirroring: {self.mirror}"
            )
            self.info_label.config(text=info_text)

        except Exception as e:
            logging.error(f"Error in update_view: {e}")

    def rotate_right(self):
        self.rotation_angle = (self.rotation_angle - 90) % 360
        self.update_view()

    def rotate_left(self):
        self.rotation_angle = (self.rotation_angle + 90) % 360
        self.update_view()

    def mirror_image(self):
        self.mirror = not self.mirror
        self.update_view()

    def toggle_display_mode(self):
        if self.display_mode == 'magnitude':
            self.display_mode = 'phase'
            self.toggle_button.config(text='Phase')
        else:
            self.display_mode = 'magnitude'
            self.toggle_button.config(text='Mag')
        self.update_view()

    def update_colormap(self, event):
        self.colormap = self.colormap_var.get()
        self.update_view()

    def update_window(self, event=None):
        self.window_level = self.level_var.get()
        self.window_width = self.width_var.get()
        self.update_view()

    def toggle_normalization(self):
        self.normalize_slice = not self.normalize_slice
        self.update_view()

    def on_spinbox_scroll(self, event, spinbox, var):
        
        current_value = int(spinbox.get())
        if event.delta > 0 or event.num == 4:
            if current_value < int(spinbox.cget('to')):
                var.set(current_value + 1)
        elif event.delta < 0 or event.num == 5:
            if current_value > int(spinbox.cget('from')):
                var.set(current_value - 1)
        self.update_view()


    def update_index(self, event, spinbox, var, index):
        try:
            value = int(spinbox.get())
            var.set(value)
            self.current_indices[index] = value
            self.update_view()
        except ValueError:
            logging.error(f"Invalid value entered for dimension {index}: {spinbox.get()}")
            spinbox.set(self.current_indices[index])

    def save_image(self):
        try:
            current_slice = self.get_current_slice()
            if current_slice is not None and current_slice.ndim == 2:
                image = np.abs(current_slice)

                # Apply rotation
                if self.rotation_angle != 0:
                    image = np.rot90(image, self.rotation_angle // 90)

                # Apply mirroring
                if self.mirror:
                    image = np.fliplr(image)

                filename = tk.filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png"), ("All files", "*.*")])
                if filename:
                    plt.imsave(filename, image, cmap=self.colormap)
        except Exception as e:
            logging.error(f"Error in save_image: {e}")

def start_viewer(file_path):
    root = tk.Tk()
    root.title("Array Viewer")
    root.geometry("1000x700")
    
    array = read_array_file(file_path)
    array = array / np.max(np.abs(array))  # Normalize the array for visualization
    app = ArrayViewer(root, array)
    
    root.protocol("WM_DELETE_WINDOW", root.quit)  # Quit the main loop when the window is closed
    root.mainloop()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python viewer.py path_to_file1 [path_to_file2 ...]")
    else:
        processes = []
        for file_path in sys.argv[1:]:
            process = multiprocessing.Process(target=start_viewer, args=(file_path,))
            process.start()
            processes.append(process)
        
        # Wait for all processes to finish
        for process in processes:
            process.join()
