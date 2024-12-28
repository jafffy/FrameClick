import cv2
import numpy as np
import mss
import pyautogui
import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple, List, Callable
from enum import Enum
import tkinter as tk
from queue import Queue
import logging
import sys
import platform
import os

# Configure logging to write to both file and console
log_file = 'screen_recorder.log'
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Log system information
logger.info(f"Operating System: {platform.system()} {platform.release()}")
logger.info(f"Python Version: {sys.version}")

# Configure PyAutoGUI safety
pyautogui.FAILSAFE = True

class MouseAction(Enum):
    PRESS = "press"
    MOVE = "move"
    RELEASE = "release"

@dataclass
class MouseCommand:
    action: MouseAction
    coordinates: Optional[Tuple[int, int]] = None

class ControlWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Screen Recorder Control")
        self.root.geometry("200x100")
        self.stop_requested = False
        
        stop_button = tk.Button(self.root, text="Stop Recording", command=self.request_stop)
        stop_button.pack(expand=True)
        
    def request_stop(self):
        self.stop_requested = True
        
    def should_stop(self):
        self.root.update()
        return self.stop_requested
        
    def close(self):
        self.root.destroy()

class RegionSelector:
    def __init__(self):
        try:
            self.root = tk.Tk()
            # Special handling for macOS
            if platform.system() == 'Darwin':
                self.root.attributes('-transparent', True)
            self.root.attributes('-alpha', 0.3)
            self.root.attributes('-topmost', True)
            
            # Get screen dimensions
            self.screen_width = self.root.winfo_screenwidth()
            self.screen_height = self.root.winfo_screenheight()
            
            # Set window size
            self.root.geometry(f"{self.screen_width}x{self.screen_height}+0+0")
            
            self.canvas = tk.Canvas(self.root, highlightthickness=0)
            self.canvas.pack(fill='both', expand=True)
            
            self.start_x = None
            self.start_y = None
            self.rect = None
            self.region = None
            
            self.canvas.bind('<Button-1>', self.on_press)
            self.canvas.bind('<B1-Motion>', self.on_drag)
            self.canvas.bind('<ButtonRelease-1>', self.on_release)
            
            # Add escape key binding to cancel
            self.root.bind('<Escape>', lambda e: self.root.quit())
            
        except Exception as e:
            logger.error(f"Failed to initialize window: {e}")
            raise

    def on_press(self, event):
        self.start_x = max(0, min(event.x, self.screen_width))
        self.start_y = max(0, min(event.y, self.screen_height))
        if self.rect:
            self.canvas.delete(self.rect)
            
    def on_drag(self, event):
        if self.rect:
            self.canvas.delete(self.rect)
        current_x = max(0, min(event.x, self.screen_width))
        current_y = max(0, min(event.y, self.screen_height))
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, current_x, current_y,
            outline='red', width=2
        )
        
    def on_release(self, event):
        if self.start_x is None or self.start_y is None:
            return
            
        end_x = max(0, min(event.x, self.screen_width))
        end_y = max(0, min(event.y, self.screen_height))
        
        x1, y1 = min(self.start_x, end_x), min(self.start_y, end_y)
        x2, y2 = max(self.start_x, end_x), max(self.start_y, end_y)
        
        # Ensure minimum size
        if x2 - x1 < 10 or y2 - y1 < 10:
            logger.warning("Selected region too small, please try again")
            return
            
        self.region = {'top': y1, 'left': x1, 'width': x2-x1, 'height': y2-y1}
        self.root.quit()
        
    def get_region(self) -> Optional[dict]:
        try:
            self.root.mainloop()
            self.root.destroy()
            return self.region
        except Exception as e:
            logger.error(f"Error in region selection: {e}")
            return None

class ScreenRecorder:
    def __init__(self, region: dict, callback_fn: Callable[[np.ndarray], Optional[MouseCommand]], control_window: ControlWindow):
        if not region:
            raise ValueError("Invalid region")
            
        self.region = region
        self.callback_fn = callback_fn
        self.control_window = control_window
        try:
            self.sct = mss.mss()
        except Exception as e:
            logger.error(f"Failed to initialize screen capture: {e}")
            raise
            
        self.frames: List[np.ndarray] = []
        self.is_recording = False
        self.frame_queue = Queue()
        self.command_queue = Queue()
        
    def capture_frame(self) -> Optional[np.ndarray]:
        try:
            screenshot = self.sct.grab(self.region)
            frame = np.array(screenshot)
            return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        except Exception as e:
            logger.error(f"Error capturing frame: {e}")
            return None
    
    def record_frames(self):
        while self.is_recording:
            frame = self.capture_frame()
            if frame is not None:
                self.frames.append(frame)
                self.frame_queue.put(frame)
            time.sleep(1/30)  # Limit to ~30 FPS
            
    def process_frames(self):
        while self.is_recording:
            try:
                if not self.frame_queue.empty():
                    frame = self.frame_queue.get()
                    command = self.callback_fn(frame)
                    if command:
                        self.command_queue.put(command)
            except Exception as e:
                logger.error(f"Error processing frame: {e}")
                    
    def execute_commands(self):
        while self.is_recording:
            try:
                if not self.command_queue.empty():
                    command = self.command_queue.get()
                    if command.action == MouseAction.PRESS and command.coordinates:
                        pyautogui.mouseDown(x=command.coordinates[0], y=command.coordinates[1])
                    elif command.action == MouseAction.MOVE and command.coordinates:
                        pyautogui.moveTo(x=command.coordinates[0], y=command.coordinates[1])
                    elif command.action == MouseAction.RELEASE:
                        pyautogui.mouseUp()
            except Exception as e:
                logger.error(f"Error executing mouse command: {e}")
                    
    def start_recording(self):
        self.is_recording = True
        
        threads = [
            threading.Thread(target=self.record_frames, daemon=True),
            threading.Thread(target=self.process_frames, daemon=True),
            threading.Thread(target=self.execute_commands, daemon=True)
        ]
        
        for thread in threads:
            thread.start()
        
        logger.info("Recording started. Click 'Stop Recording' to stop...")
        try:
            while self.is_recording:
                if self.control_window.should_stop():
                    self.stop_recording()
                time.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in recording loop: {e}")
            self.stop_recording()
    
    def stop_recording(self):
        self.is_recording = False
        logger.info("Recording stopped")
        
    def save_video(self, output_path: str, fps: int = 30):
        if not self.frames:
            logger.error("No frames to save")
            return
            
        try:
            height, width = self.frames[0].shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            for frame in self.frames:
                out.write(frame)
                
            out.release()
            logger.info(f"Video saved to {output_path}")
        except Exception as e:
            logger.error(f"Error saving video: {e}")

def example_callback(frame: np.ndarray) -> Optional[MouseCommand]:
    """
    Example callback function that processes frames and returns mouse commands.
    You can modify this function to implement your own mouse control logic.
    """
    return None

def main():
    try:
        # Let user select region
        logger.info("Select the screen region to record (press ESC to cancel)...")
        region_selector = RegionSelector()
        region = region_selector.get_region()
        
        if not region:
            logger.error("No region selected or selection cancelled")
            return
            
        # Create control window
        control_window = ControlWindow()
            
        # Create and start recorder
        recorder = ScreenRecorder(region, example_callback, control_window)
        recorder.start_recording()
        
        # Save the recording
        recorder.save_video("output.mp4")
        
        # Clean up
        control_window.close()
        
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 