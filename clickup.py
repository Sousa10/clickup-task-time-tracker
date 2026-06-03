import tkinter as tk
import requests
import time as time_module
import os
from tkinter import messagebox

CONFIG_FILE = "config.ini"

# ClickUp workspace ID
WORKSPACE_ID = '37266601'

# Get your user ID
def get_user_id(api_token):
    url = 'https://api.clickup.com/api/v2/user'
    headers = {"Authorization": api_token}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()['user']['id']
    else:
        print("Failed to retrieve user information")
        return None

# Fetch tasks assigned to you with status "In Progress"
def get_my_in_progress_tasks(api_token, user_id):
    url = f'https://api.clickup.com/api/v2/team/{WORKSPACE_ID}/task'
    params = {
        'assignees[]': user_id,  # Filter tasks assigned to this user ID
        'status': 'In Progress',  # Filter for "In Progress" status
        'include_closed': False,  # Optionally include only open tasks
        'subtasks': True  # Include subtasks, if applicable
    }
    headers = {"Authorization": api_token}
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        tasks = response.json()['tasks']
        # Further filter tasks to ensure none with "Canceled" status are included
        filtered_tasks = [
            (task['name'], task['id']) 
            for task in tasks 
            if task['status']['status'].lower() == 'in progress'
        ]
        return filtered_tasks
    else:
        print("Failed to retrieve tasks")
        return []

# Save API token in a config file
def save_api_token(api_token):
    with open(CONFIG_FILE, "w") as f:
        f.write(api_token)

# Load API token from config file
def load_api_token():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return f.read().strip()
    return None
    
def parse_clickup_error(response):
    try:
        error = response.json()
    except ValueError:
        return response.text or f"HTTP {response.status_code}"

    if isinstance(error, dict):
        if error.get("err"):
            return error["err"]
        if error.get("message"):
            return error["message"]

    return str(error)


def friendly_clickup_error(message):
    message_lower = message.lower()
    if "time tracking is not available" in message_lower:
        return (
            "Time Tracking is not available for this ClickUp workspace. "
            "Ask a workspace owner/admin to enable the Time Tracking ClickApp or check the plan limits."
        )
    if "advanced time tracking" in message_lower:
        return (
            "This workspace reached its Advanced Time Tracking limit. "
            "The app is using plain task time logging now; try again with the latest executable."
        )
    return message


# Log hours worked on a task
def log_hours(api_token, task_id, start_time, end_time, time_spent):
    url = f'https://api.clickup.com/api/v2/task/{task_id}/time'

    start_time = int(start_time)
    end_time = int(end_time)
    time_spent = int(time_spent)

    # Ensure time_spent is within a valid range
    if not (0 < time_spent < 24 * 3600000):  # Less than 24 hours
        return False, "Invalid time duration."

    data = {
        'start': start_time,
        'end': end_time,
        'time': time_spent  # Time spent in milliseconds
    }
    headers = {
        "Authorization": api_token,
        "Content-Type": "application/json"
    }
    print("Request URL:", url)  # Print the URL
    print("Request Data:", data)  # Print the data being sent

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
    except requests.RequestException as exc:
        message = f"Network error: {exc}"
        print(message)
        return False, message

    print("Response Status Code:", response.status_code)
    print("Response Content:", response.text)
    if response.status_code in (200, 201):
        print("Hours logged successfully")
        return True, "Hours logged successfully!"

    message = friendly_clickup_error(parse_clickup_error(response))
    print("Failed to log hours", message)
    return False, message

def get_existing_time_entries(api_token, task_id):
    url = f'https://api.clickup.com/api/v2/task/{task_id}/time'
    headers = {
        "Authorization": api_token,
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as exc:
        print("Failed to retrieve time entries", exc)
        return []

    if response.status_code == 200:
        time_entries = response.json().get('data', [])
        print(f"Existing time entries for task {task_id}:")
        for entry in time_entries:
            start = entry.get('start')
            end = entry.get('end')
            duration = entry.get('duration')
            if start is not None and end is None and duration and duration > 0:
                end = int(start) + int(duration)
            print(f"Start: {start}, End: {end}")
        return time_entries 
    else:
        print("Failed to retrieve time entries", parse_clickup_error(response))
        return []

# Function to find a non-overlapping time interval
def find_time_gap(existing_entries, time_spent):
    # Flatten the intervals from all entries
    all_intervals = []
    for entry in existing_entries:
        start = entry.get('start')
        end = entry.get('end')
        duration = entry.get('duration')
        if start is not None and end is None and duration and duration > 0:
            end = int(start) + int(duration)
        if start is not None and end is not None:
            all_intervals.append({'start': int(start), 'end': int(end)})

        for interval in entry.get('intervals', []):
            start = interval.get('start')
            end = interval.get('end')
            
            # Skip intervals that have None as start or end
            if start is None or end is None:
                continue
            
            # Convert the start and end times from strings to integers for comparison
            interval['start'] = int(start)
            interval['end'] = int(end)
            all_intervals.append(interval)
    
    # Sort all intervals by the start time
    all_intervals.sort(key=lambda x: x['start'])
    
    # If no gap is found, place the new entry after the last one
    if all_intervals:
        last_end_time = all_intervals[-1]['end']
        return last_end_time + 1, last_end_time + 1 + time_spent
    
    # If no intervals exist, use the current time as the end time
    current_time = int(time_module.time() * 1000)
    return current_time - time_spent, current_time

# GUI Application
class ClickUpApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.api_token = load_api_token()

        # Example button that triggers the log_manual_hours function
        tk.Button(self, text="Log Hours", command=lambda: self.log_manual_hours("task_id", self.manual_entry)).pack(pady=10)
        
        if self.api_token:
            self.show_task_logger()
        else:
            self.show_token_input()
    
    def initialize_ui(self):
        # Refresh button to reload tasks
        self.refresh_button = tk.Button(self, text="Refresh Tasks", command=self.load_tasks, bg="#4CAF50", fg="white",  width=30, height=2)
        self.refresh_button.grid(row=0, column=0, padx=10, pady=10)
    
    def load_tasks(self):
        self.show_task_logger()

    def show_token_input(self):
        for widget in self.winfo_children():
            widget.destroy()
        self.title("Enter ClickUp API Token")
        self.geometry("300x150")

        tk.Label(self, text="Enter your ClickUp API Token:").pack(pady=10)
        self.token_entry = tk.Entry(self, show="*")
        self.token_entry.pack(pady=5)

        tk.Button(self, text="Save Token", command=self.save_and_proceed).pack(pady=10)

    def save_and_proceed(self):
        self.api_token = self.token_entry.get()
        if self.api_token:
            save_api_token(self.api_token)
            self.show_task_logger()
        
    def show_task_logger(self):
        for widget in self.winfo_children():
            widget.destroy()
        
        # Create feedback label for user messages
        self.feedback_label = tk.Label(
            self,
            text="",
            fg="green",
            font=('Helvetica', 10, 'bold'),
            anchor="w",
            justify="left",
            wraplength=760
        )
        self.feedback_label.grid(row=1, column=0, columnspan=6, padx=10, pady=(0, 10), sticky="ew")

        self.initialize_ui()  # Ensure UI elements like the refresh button are recreated

        user_id = get_user_id(self.api_token)
        if user_id:
            self.tasks = get_my_in_progress_tasks(self.api_token, user_id)

            # Calculate the required height based on the number of tasks
            num_tasks = len(self.tasks)
            row_height = 42  # Height per row in pixels
            header_height = 90  # Space for the header row and wrapped feedback message
            total_height = header_height + (num_tasks * row_height)
            window_height = max(total_height, 300)  # Ensure a minimum height of 300 pixels

            self.title("ClickUp Task Time Logger")
            self.geometry(f"820x{window_height}+700+400")
            
            self.start_times = {}  # To store start times for each task
            self.elapsed_time_vars = {}  # To store elapsed time variables for each task
            # Create headers for the table
            headers = ["Task", "Manual Hours", "Log Manual Hours", "Start", "Stop", "Elapsed Time"]
            for col, header in enumerate(headers):
                tk.Label(self, text=header, font=('Helvetica', 10, 'bold')).grid(row=2, column=col, padx=5, pady=5)
            
            # Create a row for each task
            for row, (task_name, task_id) in enumerate(self.tasks, start=3):
                self.create_task_row(row, task_name, task_id)
        else:
            tk.Label(
                self,
                text="Failed to retrieve tasks. Check the API token, network, and ClickUp access.",
                fg="red",
                font=('Helvetica', 10, 'bold')
            ).grid(row=2, column=0, columnspan=6, padx=10, pady=20)
    
    def create_task_row(self, row, task_name, task_id):
        tk.Label(self, text=task_name).grid(row=row, column=0, padx=5, pady=5, sticky="w")

        manual_entry = tk.Entry(self, fg='grey')
        manual_entry.insert(0, 'Enter time as HH:MM')
        manual_entry.bind("<FocusIn>", lambda event, e=manual_entry: self.clear_entry(e))
        manual_entry.bind("<FocusOut>", lambda event, e=manual_entry: self.add_placeholder(e))

        manual_entry.grid(row=row, column=1, padx=5, pady=5)

        log_button = tk.Button(self, text="Manual Hours", 
                                command=lambda t_id=task_id, entry=manual_entry: self.log_manual_hours(t_id, entry))
        log_button.grid(row=row, column=2, padx=5, pady=5)
        
        start_button = tk.Button(self, text="Start", command=lambda t_id=task_id: self.start_tracking(t_id))
        start_button.grid(row=row, column=3, padx=5, pady=5)
        
        stop_button = tk.Button(self, text="Stop", command=lambda t_id=task_id: self.stop_tracking(t_id))
        stop_button.grid(row=row, column=4, padx=5, pady=5)
        
        
        elapsed_time_var = tk.StringVar(self, value="00:00:00")
        elapsed_time_label = tk.Label(self, textvariable=elapsed_time_var)
        elapsed_time_label.grid(row=row, column=5, padx=5, pady=5)

        # Store variables to reference later
        self.start_times[task_id] = None
        self.elapsed_time_vars[task_id] = elapsed_time_var

    def clear_entry(self, entry):
        """Clears the entry if it contains the default placeholder text."""
        if entry.get() == 'Enter time as HH:MM' and entry.cget('fg') == 'grey':
            entry.delete(0, tk.END)
            entry.config(fg='black')  # Change text color to black when user focuses

    def add_placeholder(self, entry):
        """Adds placeholder text if the entry is empty."""
        if not entry.get():
            entry.config(fg='grey')
            entry.insert(0, 'Enter time as HH:MM')

    def log_manual_hours(self, task_id, entry):
        time_str = entry.get()
        if self.validate_time(time_str):
            hours, minutes = map(int, time_str.split(':'))
            time_spent = hours * 3600 * 1000 + minutes * 60 * 1000  # Convert to milliseconds

            # Retrieve existing time entries for the task
            existing_entries = get_existing_time_entries(self.api_token, task_id)
            
            # Find a suitable time gap to log the new entry
            start_time, end_time = find_time_gap(existing_entries, time_spent)
            
            print(f"Logging {hours} hours and {minutes} minutes from {start_time} to {end_time}")

            success, message = log_hours(self.api_token, task_id, start_time, end_time, time_spent)

            if success:
                self.feedback_label.config(text=message, fg="green")
            else:
                self.feedback_label.config(text=f"Failed to log hours: {message}", fg="red")
            
            # Clear the input field after logging
            entry.delete(0, tk.END)

            # Schedule the feedback label to clear after 4 seconds (4000 milliseconds)
            self.after(4000, self.clear_feedback_label)
        else:
            messagebox.showerror("Invalid Time", "Please enter time in HH:MM format.")
        
    def validate_time(self, time_str):
        try:
            hours, minutes = map(int, time_str.split(':'))
            if 0 <= hours < 24 and 0 <= minutes < 60:
                return True
        except ValueError:
            pass
        return False
    
    def clear_feedback_label(self):
        self.feedback_label.config(text="")

    def start_tracking(self, task_id):
        self.start_times[task_id] = time_module.time()
        self.update_clock(task_id)
        print(f"Started tracking time for task: {task_id}")

    def stop_tracking(self, task_id):
        start_time = self.start_times[task_id]
        if start_time:
            end_time = time_module.time()
            elapsed_seconds = end_time - start_time
        
            # Ensure that elapsed time is valid and not negative or zero
            if elapsed_seconds > 0:
                time_spent = int(elapsed_seconds * 1000)  # Time spent in milliseconds
                start_time = int(start_time * 1000)  # Convert start time to milliseconds
                end_time = int(end_time * 1000)  # Convert end time to milliseconds
                print(f"Elapsed time (seconds): {elapsed_seconds}")
                print(f"Time spent (milliseconds): {time_spent}")
                
                # Log the hours using the time spent
                success, message = log_hours(self.api_token, task_id, start_time, end_time, time_spent)

                if success:
                    self.feedback_label.config(text=message, fg="green")
                    # Schedule the feedback label to clear after 4 seconds (4000 milliseconds)
                    self.after(4000, self.clear_feedback_label)
                else:
                    self.feedback_label.config(text=f"Failed to log hours: {message}", fg="red")
                    print(f"Stopped tracking time for task, logged {time_spent / 3600000:.2f} hours")
            else:
                print("Invalid elapsed time, unable to log hours")
            
            # Reset start time and elapsed time display
            self.start_times[task_id] = None
            self.elapsed_time_vars[task_id].set("00:00:00")
        else:
            print("No task is currently being tracked")

    def update_clock(self, task_id):
        start_time = self.start_times[task_id]
        if start_time:
            elapsed_time = time_module.time() - start_time
            hours, remainder = divmod(int(elapsed_time), 3600)
            minutes, seconds = divmod(remainder, 60)
            self.elapsed_time_vars[task_id].set(f"{hours:02}:{minutes:02}:{seconds:02}")
            self.after(1000, self.update_clock, task_id)  # Update the clock every second

if __name__ == "__main__":
    app = ClickUpApp()
    app.mainloop()
