# ClickUp Task Time Tracker

This is a desktop application built using Python and Tkinter for tracking and logging time spent on ClickUp tasks. The app allows users to manually log hours or track time automatically using start and stop buttons for each task.

## Features

- **List of In-Progress Tasks**: Automatically fetches and displays tasks that are currently in progress.
- **Manual Hour Logging**: Allows users to input hours worked on a task and log them manually.
- **Automatic Time Tracking**: Users can start and stop a timer to automatically track time for each task.
- **Task Timer**: Displays the elapsed time for each task while tracking.
- **ClickUp Integration**: Connects to the ClickUp API to retrieve tasks and log time entries.
- **User Authentication**: Users can input their ClickUp API token to access their tasks.

## Installation

### Prerequisites

Ensure that you have the following installed:

- **Python 3.x**
- **pip** (Python package manager)

### Required Libraries

You will need to install the following Python libraries:

```
pip install requests
pip install tkinter
```

## Package the application (no console window):
`pyinstaller --onefile --noconsole clickup.py`

## Usage
### 1. Input ClickUp API Token
When you first open the application, it will prompt you to enter your ClickUp API token.
This token can be obtained from your ClickUp account settings under Apps.
Once entered, the token is saved locally, and the list of your "In Progress" tasks will be fetched.

### 2. Viewing Tasks
The main screen displays all your tasks that are currently in progress.
For each task, you will see the following:
Task Name
Manual Hours Input Field
Log Manual Hours Button
Start and Stop Buttons for automatic time tracking
Elapsed Time counter

#### 3. Manual Hour Logging
To manually log hours for a task:
Input the number of hours in the Manual Hours field.
Click the Manual Hours button.
If successful, a confirmation message will appear and the input field will clear automatically.

### 4. Time Tracking
To track time automatically:
Click Start next to the task you want to track.
The elapsed time will begin counting.
Click Stop to stop tracking, and the time will be logged to ClickUp automatically.

### 5. Feedback
The application provides feedback for actions such as:
Success: When hours are logged successfully.
Failure: When logging fails (e.g., due to overlap with another time entry).
Validation Errors: If invalid input is provided (e.g., non-numeric hours).

### 6. Closing the Application
You can close the application by clicking the window’s close button.
If you want to reset your API token, delete the locally saved token and restart the app.

## File Structure

Copy code
.
├── clickup.py                 # Main application file
├── README.md                  # Documentation file
├── pipfile         # (Optional) List of dependencies
└── dist/                      # (Generated after packaging) Executable files

## Customization
You can customize the application by:

### Adding More ClickUp Features: 
Modify the ClickUp API integration to support additional functionality such as task creation, editing, or filtering by different task statuses.
### Enhancing the UI: 
Improve the design of the application by adding more Tkinter widgets or using a GUI framework like ttk for enhanced styling.
### Storing API Tokens Securely: 
Currently, the API token is stored locally in plain text. You can enhance security by encrypting the token or using a more secure storage mechanism.
## Troubleshooting
### Task List Not Loading: 
Ensure your ClickUp API token is valid and that you have tasks in the "In Progress" state.
## Known Issues
Token Storage: API tokens are stored in plain text, which may be insecure for some users. Consider implementing a more secure storage method for sensitive data.
No Offline Mode: The app relies on real-time interaction with the ClickUp API, so it will not function without internet access.
## License
This project is open-source and free to use under the MIT License.

## Contributions
Contributions are welcome! Feel free to open issues or submit pull requests for improvements.
