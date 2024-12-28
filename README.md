# Screen Region Recorder with Mouse Control

This Python application allows you to record a selected region of your screen while capturing and executing mouse controls. It supports frame-by-frame processing with a callback function that can trigger mouse actions.

## Features

- Screen region selection via click-and-drag
- Continuous frame capture at 30 FPS
- Custom callback processing for each frame
- Mouse control actions (press, move, release)
- MP4 video recording
- Thread-safe design

## Requirements

- Python 3.7+
- Dependencies listed in `requirements.txt`

## Installation

1. Clone this repository
2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Run the script:
```bash
python screen_recorder.py
```

2. Select the screen region by clicking and dragging to create a rectangle
3. The recording will start automatically
4. Press 'q' to stop recording
5. The video will be saved as 'output.mp4'

## Customizing the Callback Function

The `example_callback` function in `screen_recorder.py` can be modified to implement your own mouse control logic. Here's an example of how to implement a custom callback:

```python
def custom_callback(frame: np.ndarray) -> Optional[MouseCommand]:
    # Analyze the frame
    # Return a MouseCommand based on your analysis
    return MouseCommand(
        action=MouseAction.PRESS,
        coordinates=(100, 100)
    )
```

The callback function receives each frame as a numpy array and can return one of three mouse actions:
- PRESS: Mouse down at specific coordinates
- MOVE: Move mouse to coordinates
- RELEASE: Release mouse button

## Error Handling

The application includes error handling for:
- Invalid screen regions
- Failed mouse commands
- Video encoding issues

Errors are logged using Python's built-in logging module.

## Notes

- The application uses multiple threads to handle frame capture, processing, and mouse control separately
- Frame capture is limited to 30 FPS to maintain performance
- Mouse actions are executed in real-time as they are returned by the callback function 