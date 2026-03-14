import tkinter as tk
from tkinter import filedialog, messagebox

class VideoTrimmer:
    def __init__(self, master):
        self.master = master
        master.title("Video Trimmer")

        self.label = tk.Label(master, text="Select Video File:")
        self.label.pack()

        self.select_button = tk.Button(master, text="Browse", command=self.load_file)
        self.select_button.pack()

        self.start_label = tk.Label(master, text="Start Time (seconds):")
        self.start_label.pack()

        self.start_time = tk.Entry(master)
        self.start_time.pack()

        self.end_label = tk.Label(master, text="End Time (seconds):")
        self.end_label.pack()

        self.end_time = tk.Entry(master)
        self.end_time.pack()

        self.trim_button = tk.Button(master, text="Trim Video", command=self.trim_video)
        self.trim_button.pack()

    def load_file(self):
        self.file_path = filedialog.askopenfilename()
        if not self.file_path:
            messagebox.showwarning("Warning", "No file selected.")

    def trim_video(self):
        start = self.start_time.get()
        end = self.end_time.get()

        if not hasattr(self, 'file_path') or not self.file_path:
            messagebox.showerror("Error", "Please select a video file first!")
            return

        if not start or not end:
            messagebox.showerror("Error", "Please enter start and end times.")
            return

        # Here you would add the logic to process the video trimming
        # e.g., using moviepy or another video editing library
        messagebox.showinfo("Success", f"Video trimmed from \n{start} to {end} seconds.")

if __name__ == '__main__':
    root = tk.Tk()
    video_trimmer = VideoTrimmer(root)
    root.mainloop()