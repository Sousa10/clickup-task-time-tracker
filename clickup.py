import tkinter as tk
import requests
import time as time_module
import os
import configparser
from datetime import datetime, timezone
from tkinter import messagebox

CONFIG_FILE = "config.ini"
SUPABASE_REST_TIMEOUT = 30

# ClickUp workspace ID
WORKSPACE_ID = '37266601'


def utc_iso_from_ms(timestamp_ms):
    return datetime.fromtimestamp(int(timestamp_ms) / 1000, timezone.utc).isoformat()


def normalize_supabase_url(url):
    normalized_url = url.strip().strip('"').strip("'").rstrip("/")
    for suffix in ("/rest/v1", "/rest"):
        if normalized_url.endswith(suffix):
            normalized_url = normalized_url[:-len(suffix)]
            break
    return normalized_url.rstrip("/")

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

def default_config():
    return {
        "clickup_api_token": "",
        "supabase_url": "",
        "supabase_anon_key": ""
    }


def load_app_config():
    config = default_config()
    if not os.path.exists(CONFIG_FILE):
        return config

    with open(CONFIG_FILE, "r") as f:
        content = f.read().strip()

    if not content:
        return config

    # Backward compatibility with the old config.ini that contained only the ClickUp token.
    if not content.startswith("["):
        config["clickup_api_token"] = content
        return config

    parser = configparser.ConfigParser()
    parser.read_string(content)
    config["clickup_api_token"] = parser.get("clickup", "api_token", fallback="")
    config["supabase_url"] = parser.get("supabase", "url", fallback="")
    config["supabase_anon_key"] = parser.get("supabase", "anon_key", fallback="")
    return config


def save_app_config(config):
    parser = configparser.ConfigParser()
    parser["clickup"] = {
        "api_token": config.get("clickup_api_token", "").strip()
    }
    parser["supabase"] = {
        "url": normalize_supabase_url(config.get("supabase_url", "")),
        "anon_key": config.get("supabase_anon_key", "").strip()
    }
    with open(CONFIG_FILE, "w") as f:
        parser.write(f)


def supabase_is_configured(config):
    return bool(config.get("supabase_url") and config.get("supabase_anon_key"))
    
def parse_api_error(response):
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


def friendly_supabase_error(message):
    message_lower = message.lower()
    if "relation" in message_lower and "does not exist" in message_lower:
        return "Supabase table is missing. Run the supabase_schema.sql script in your Supabase SQL editor."
    if "invalid api key" in message_lower or "jwt" in message_lower:
        return "Supabase credentials are invalid. Check the project URL and anon key in Settings."
    if "invalid path specified" in message_lower:
        return "Supabase URL looks wrong. In Settings, use only https://your-project-ref.supabase.co, without /rest/v1 or any extra path."
    if "permission denied for table" in message_lower:
        return "Supabase table permissions are missing. Rerun the latest supabase_schema.sql script in the Supabase SQL editor."
    return message


def supabase_headers(config, prefer=None):
    headers = {
        "apikey": config["supabase_anon_key"],
        "Authorization": f"Bearer {config['supabase_anon_key']}",
        "Content-Type": "application/json"
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def supabase_rest_url(config, table_name):
    return f"{normalize_supabase_url(config['supabase_url'])}/rest/v1/{table_name}"


def upsert_supabase_task(config, task_id, task_name):
    url = supabase_rest_url(config, "tasks")
    params = {"on_conflict": "clickup_task_id"}
    data = {
        "clickup_task_id": task_id,
        "name": task_name,
        "last_seen_at": datetime.now(timezone.utc).isoformat()
    }

    try:
        response = requests.post(
            url,
            headers=supabase_headers(config, "resolution=merge-duplicates"),
            params=params,
            json=data,
            timeout=SUPABASE_REST_TIMEOUT
        )
    except requests.RequestException as exc:
        return False, f"Network error saving task to Supabase: {exc}"

    if response.status_code in (200, 201, 204):
        return True, "Task saved."

    return False, friendly_supabase_error(parse_api_error(response))


def save_time_entry(config, task_id, task_name, start_time, end_time, time_spent, source, user_id=None):
    if not supabase_is_configured(config):
        return False, "Supabase is not configured. Open Settings and add the Supabase URL and anon key."

    start_time = int(start_time)
    end_time = int(end_time)
    time_spent = int(time_spent)

    if not (0 < time_spent < 24 * 3600000):  # Less than 24 hours
        return False, "Invalid time duration."

    success, message = upsert_supabase_task(config, task_id, task_name)
    if not success:
        return False, message

    url = supabase_rest_url(config, "time_entries")
    data = {
        "clickup_task_id": task_id,
        "task_name": task_name,
        "clickup_user_id": str(user_id) if user_id else None,
        "start_time": utc_iso_from_ms(start_time),
        "end_time": utc_iso_from_ms(end_time),
        "start_ms": start_time,
        "end_ms": end_time,
        "duration_ms": time_spent,
        "duration_minutes": round(time_spent / 60000, 2),
        "source": source
    }
    print("Supabase Request URL:", url)
    print("Supabase Request Data:", data)

    try:
        response = requests.post(
            url,
            headers=supabase_headers(config, "return=representation"),
            json=data,
            timeout=SUPABASE_REST_TIMEOUT
        )
    except requests.RequestException as exc:
        message = f"Network error saving time to Supabase: {exc}"
        print(message)
        return False, message

    print("Supabase Response Status Code:", response.status_code)
    print("Supabase Response Content:", response.text)
    if response.status_code in (200, 201, 204):
        print("Hours saved successfully")
        return True, "Hours saved to Supabase!"

    message = friendly_supabase_error(parse_api_error(response))
    print("Failed to save hours", message)
    return False, message


def get_existing_time_entries(config, task_id):
    if not supabase_is_configured(config):
        return []

    url = supabase_rest_url(config, "time_entries")
    params = {
        "select": "start_ms,end_ms,duration_ms",
        "clickup_task_id": f"eq.{task_id}",
        "order": "start_ms.asc"
    }
    try:
        response = requests.get(
            url,
            headers=supabase_headers(config),
            params=params,
            timeout=SUPABASE_REST_TIMEOUT
        )
    except requests.RequestException as exc:
        print("Failed to retrieve Supabase time entries", exc)
        return []

    if response.status_code == 200:
        entries = response.json()
        print(f"Existing Supabase time entries for task {task_id}:")
        for entry in entries:
            print(f"Start: {entry.get('start_ms')}, End: {entry.get('end_ms')}")
        return entries

    print("Failed to retrieve Supabase time entries", friendly_supabase_error(parse_api_error(response)))
    return []

# Function to find a non-overlapping time interval
def find_time_gap(existing_entries, time_spent):
    # Flatten the intervals from all entries
    all_intervals = []
    for entry in existing_entries:
        start_ms = entry.get('start_ms')
        end_ms = entry.get('end_ms')
        if start_ms is not None and end_ms is not None:
            all_intervals.append({'start': int(start_ms), 'end': int(end_ms)})

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
        self.app_config = load_app_config()
        self.api_token = self.app_config.get("clickup_api_token", "")
        self.current_user_id = None
        self.task_names = {}
        
        if self.api_token and supabase_is_configured(self.app_config):
            self.show_task_logger()
        else:
            self.show_config_input()
    
    def initialize_ui(self):
        # Refresh button to reload tasks
        self.refresh_button = tk.Button(self, text="Refresh Tasks", command=self.load_tasks, bg="#4CAF50", fg="white", width=30, height=2)
        self.refresh_button.grid(row=0, column=0, padx=10, pady=10)

        self.settings_button = tk.Button(self, text="Settings", command=self.show_config_input, width=12, height=2)
        self.settings_button.grid(row=0, column=1, padx=5, pady=10, sticky="w")
    
    def load_tasks(self):
        self.show_task_logger()

    def show_config_input(self):
        for widget in self.winfo_children():
            widget.destroy()
        self.title("App Settings")
        self.geometry("580x260")

        tk.Label(self, text="ClickUp API Token:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.token_entry = tk.Entry(self, show="*")
        self.token_entry.insert(0, self.app_config.get("clickup_api_token", ""))
        self.token_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        tk.Label(self, text="Supabase URL:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.supabase_url_entry = tk.Entry(self)
        self.supabase_url_entry.insert(0, self.app_config.get("supabase_url", ""))
        self.supabase_url_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        tk.Label(self, text="Supabase Anon Key:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        self.supabase_key_entry = tk.Entry(self, show="*")
        self.supabase_key_entry.insert(0, self.app_config.get("supabase_anon_key", ""))
        self.supabase_key_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

        tk.Button(self, text="Save Settings", command=self.save_and_proceed, bg="#4CAF50", fg="white").grid(row=3, column=1, padx=10, pady=15, sticky="e")

        self.columnconfigure(1, weight=1)

    def save_and_proceed(self):
        self.app_config = {
            "clickup_api_token": self.token_entry.get().strip(),
            "supabase_url": normalize_supabase_url(self.supabase_url_entry.get()),
            "supabase_anon_key": self.supabase_key_entry.get().strip()
        }
        self.api_token = self.app_config["clickup_api_token"]

        if not self.api_token:
            messagebox.showerror("Missing Setting", "Please enter the ClickUp API token.")
            return
        if not supabase_is_configured(self.app_config):
            messagebox.showerror("Missing Setting", "Please enter the Supabase URL and anon key.")
            return

        save_app_config(self.app_config)
        if self.api_token:
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
            self.current_user_id = user_id
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
            self.task_names = {}  # To store task names by ClickUp task ID
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
        self.task_names[task_id] = task_name

        manual_entry = tk.Entry(self, fg='grey')
        manual_entry.insert(0, 'Enter time as HH:MM')
        manual_entry.bind("<FocusIn>", lambda event, e=manual_entry: self.clear_entry(e))
        manual_entry.bind("<FocusOut>", lambda event, e=manual_entry: self.add_placeholder(e))

        manual_entry.grid(row=row, column=1, padx=5, pady=5)

        log_button = tk.Button(self, text="Manual Hours", 
                                command=lambda t_id=task_id, t_name=task_name, entry=manual_entry: self.log_manual_hours(t_id, t_name, entry))
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

    def log_manual_hours(self, task_id, task_name, entry):
        time_str = entry.get()
        if self.validate_time(time_str):
            hours, minutes = map(int, time_str.split(':'))
            time_spent = hours * 3600 * 1000 + minutes * 60 * 1000  # Convert to milliseconds

            # Retrieve existing time entries for the task
            existing_entries = get_existing_time_entries(self.app_config, task_id)
            
            # Find a suitable time gap to log the new entry
            start_time, end_time = find_time_gap(existing_entries, time_spent)
            
            print(f"Logging {hours} hours and {minutes} minutes from {start_time} to {end_time}")

            success, message = save_time_entry(
                self.app_config,
                task_id,
                task_name,
                start_time,
                end_time,
                time_spent,
                "manual",
                self.current_user_id
            )

            if success:
                self.feedback_label.config(text=message, fg="green")
            else:
                self.feedback_label.config(text=f"Failed to save hours: {message}", fg="red")
            
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
                
                task_name = self.task_names.get(task_id, task_id)

                # Save the hours using the time spent
                success, message = save_time_entry(
                    self.app_config,
                    task_id,
                    task_name,
                    start_time,
                    end_time,
                    time_spent,
                    "timer",
                    self.current_user_id
                )

                if success:
                    self.feedback_label.config(text=message, fg="green")
                    # Schedule the feedback label to clear after 4 seconds (4000 milliseconds)
                    self.after(4000, self.clear_feedback_label)
                else:
                    self.feedback_label.config(text=f"Failed to save hours: {message}", fg="red")
                    print(f"Stopped tracking time for task, measured {time_spent / 3600000:.2f} hours")
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
