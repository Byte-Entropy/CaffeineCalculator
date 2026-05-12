import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import ttk, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import datetime

HALF_LIFE = 5.0  # hours
COLORS = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']

def caffeine_level_at_time(intake_start_time, dose_amount, dose_duration_hours, current_time):
    """
    Calculate caffeine level from a single dose (or dose distributed over time).
    dose_duration_hours: 0 = immediate, >0 = distributed over this many hours
    Accounts for ~30 minute peak time for immediate doses.
    """
    half_life = HALF_LIFE
    PEAK_TIME = 0.5  # 30 minutes to reach peak absorption
    
    if dose_duration_hours == 0:
        # Immediate dose with absorption phase
        time_elapsed = (current_time - intake_start_time).total_seconds() / 3600
        
        if time_elapsed < 0:
            return 0
        elif time_elapsed <= PEAK_TIME:
            # Absorption phase: linear rise to peak
            return dose_amount * (time_elapsed / PEAK_TIME)
        else:
            # Decay phase from peak
            time_after_peak = time_elapsed - PEAK_TIME
            decay_factor = 0.5 ** (time_after_peak / half_life)
            return dose_amount * decay_factor
    else:
        # Dose distributed over dose_duration_hours
        time_elapsed = (current_time - intake_start_time).total_seconds() / 3600
        intake_end_time = intake_start_time + datetime.timedelta(hours=dose_duration_hours)
        
        # If current time is before intake starts, no caffeine yet
        if current_time < intake_start_time:
            return 0
        
        rate = dose_amount / dose_duration_hours
        ln2 = np.log(2)
        
        if current_time <= intake_end_time:
            # Still in intake period
            # Caffeine = rate * HL / ln(2) * (1 - 0.5^(t/HL))
            caffeine = rate * half_life / ln2 * (1 - 0.5 ** (time_elapsed / half_life))
            return caffeine
        else:
            # Absorption finished, now decaying
            time_since_end = (current_time - intake_end_time).total_seconds() / 3600
            # Caffeine at end of absorption period
            caffeine_at_end = rate * half_life / ln2 * (1 - 0.5 ** (dose_duration_hours / half_life))
            # Apply decay
            return caffeine_at_end * (0.5 ** (time_since_end / half_life))


class CaffeineTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Caffeine Tracker")
        self.root.geometry("1000x700")
        
        self.intakes = []  # List of {amount, duration_hours, start_time}
        self.intake_counter = 0
        self.reference_time = datetime.datetime.now()  # Reference point for display
        
        # Create main layout
        main_frame = ttk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create figure
        self.fig = Figure(figsize=(10, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        # Canvas for matplotlib
        self.canvas = FigureCanvasTkAgg(self.fig, master=main_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        # Bind motion event for hover tooltip
        self.canvas.mpl_connect('motion_notify_event', self.on_hover)
        
        # Create tooltip
        self.tooltip = tk.Label(self.canvas.get_tk_widget(), text="", bg="lightyellow", fg="black", padx=5, pady=2, font=("Arial", 9))
        self.tooltip.place(x=0, y=0)
        self.tooltip.place_forget()
        
        # Right panel for controls
        control_frame = ttk.Frame(main_frame, width=250)
        control_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=5)
        
        # Title
        title_label = ttk.Label(control_frame, text="Add Intake", font=("Arial", 12, "bold"))
        title_label.pack(pady=10)
        
        # Amount
        ttk.Label(control_frame, text="Amount (mg):").pack(anchor=tk.W)
        self.amount_var = tk.StringVar(value="200")
        amount_entry = ttk.Entry(control_frame, textvariable=self.amount_var, width=15)
        amount_entry.pack(anchor=tk.W, pady=(0, 10))
        
        # Dose type
        ttk.Label(control_frame, text="Dose Type:").pack(anchor=tk.W)
        self.dose_type_var = tk.StringVar(value="immediate")
        dose_type_combo = ttk.Combobox(
            control_frame,
            textvariable=self.dose_type_var,
            values=["immediate", "over time"],
            state="readonly",
            width=13
        )
        dose_type_combo.pack(anchor=tk.W, pady=(0, 10))
        dose_type_combo.bind("<<ComboboxSelected>>", self.on_dose_type_change)
        
        # Duration (hours:minutes) - initially hidden
        self.duration_label = ttk.Label(control_frame, text="Duration (HH:MM):")
        self.duration_label.pack(anchor=tk.W)
        self.duration_var = tk.StringVar(value="03:00")
        self.duration_entry = ttk.Entry(control_frame, textvariable=self.duration_var, width=15)
        self.duration_entry.pack(anchor=tk.W, pady=(0, 10))
        
        # Add button
        add_btn = ttk.Button(control_frame, text="Add Intake", command=self.add_intake)
        add_btn.pack(pady=15, fill=tk.X)
        
        # Reset button
        reset_btn = ttk.Button(control_frame, text="Reset Time to Now", command=self.reset_time)
        reset_btn.pack(pady=5, fill=tk.X)
        
        # Separator
        ttk.Separator(control_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Intakes list
        ttk.Label(control_frame, text="Current Intakes:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(10, 5))
        
        # Scrollable frame for intakes
        self.intakes_frame = ttk.Frame(control_frame)
        self.intakes_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Initially hide duration for immediate dose
        self.duration_label.pack_forget()
        self.duration_entry.pack_forget()
        
        self.update_plot()
    
    def on_hover(self, event):
        """Display time at cursor position on chart"""
        if event.inaxes != self.ax:
            self.tooltip.place_forget()
            return
        
        x_pos = event.xdata
        if x_pos is None:
            self.tooltip.place_forget()
            return
        
        # x_pos is hours from reference_time
        hover_time = self.reference_time + datetime.timedelta(hours=x_pos)
        time_str = hover_time.strftime("%H:%M")
        
        self.tooltip.config(text=time_str)
        self.tooltip.update_idletasks()  # Update to get actual size
        
        # Get tooltip size
        tooltip_width = self.tooltip.winfo_width()
        tooltip_height = self.tooltip.winfo_height()
        
        # Get actual mouse pointer position in screen coordinates
        mouse_x = self.root.winfo_pointerx()
        mouse_y = self.root.winfo_pointery()
        
        # Calculate position: above cursor, centered horizontally on cursor
        x = mouse_x - tooltip_width // 2
        y = mouse_y - tooltip_height - 5
        
        # Keep tooltip on screen
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()
        
		# if tooltip goes off left edge, move it right; if it goes off right edge, move it left; if it goes off top edge, move it below cursor
        if x < 5:
            x = 5
        if x + tooltip_width > window_width - 5:
            x = window_width - tooltip_width - 5
        if y < 5:
            y = mouse_y + 10  # Move below if no room above
        
        self.tooltip.place(x=x, y=y)
    
    def reset_time(self):
        """Reset reference time to current time"""
        self.reference_time = datetime.datetime.now()
        # Shift all intakes so they maintain their relative position
        time_delta = datetime.datetime.now() - self.reference_time
        for intake in self.intakes:
            intake['start_time'] = intake['start_time'] + time_delta
        self.update_plot()
    
    def on_dose_type_change(self, event=None):
        if self.dose_type_var.get() == "over time":
            self.duration_label.pack(anchor=tk.W)
            self.duration_entry.pack(anchor=tk.W, pady=(0, 10))
        else:
            self.duration_label.pack_forget()
            self.duration_entry.pack_forget()
    
    def add_intake(self):
        try:
            amount = float(self.amount_var.get())
            if amount <= 0:
                messagebox.showerror("Invalid Input", "Amount must be positive")
                return
            
            dose_type = self.dose_type_var.get()
            if dose_type == "immediate":
                duration_hours = 0
            else:
                duration_str = self.duration_var.get()
                parts = duration_str.split(":")
                if len(parts) != 2:
                    messagebox.showerror("Invalid Format", "Use HH:MM format")
                    return
                hours = int(parts[0])
                minutes = int(parts[1])
                duration_hours = hours + minutes / 60.0
                if duration_hours <= 0:
                    messagebox.showerror("Invalid Input", "Duration must be positive")
                    return
            
            start_time = datetime.datetime.now()
            self.intakes.append({
                'amount': amount,
                'duration_hours': duration_hours,
                'start_time': start_time,
                'id': self.intake_counter
            })
            self.intake_counter += 1
            
            self.update_plot()
            self.display_intakes_list()
            
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers")
    
    def remove_intake(self, intake_id):
        self.intakes = [i for i in self.intakes if i['id'] != intake_id]
        self.update_plot()
        self.display_intakes_list()
    
    def display_intakes_list(self):
        for widget in self.intakes_frame.winfo_children():
            widget.destroy()
        
        for i, intake in enumerate(self.intakes):
            frame = ttk.Frame(self.intakes_frame)
            frame.pack(fill=tk.X, pady=2)
            
            amount = intake['amount']
            duration = intake['duration_hours']
            if duration == 0:
                label_text = f"Intake {i+1}: {amount}mg (immediate)"
            else:
                h = int(duration)
                m = int((duration - h) * 60)
                label_text = f"Intake {i+1}: {amount}mg ({h}h {m}m)"
            
            label = ttk.Label(frame, text=label_text, width=25)
            label.pack(side=tk.LEFT)
            
            remove_btn = ttk.Button(
                frame,
                text="Remove",
                command=lambda iid=intake['id']: self.remove_intake(iid),
                width=8
            )
            remove_btn.pack(side=tk.RIGHT)
    
    def update_plot(self):
        self.ax.clear()
        
        # Time range: from earliest intake to 24 hours after reference
        if self.intakes:
            earliest = min(i['start_time'] for i in self.intakes)
            time_start = earliest
        else:
            time_start = self.reference_time
        
        time_end = self.reference_time + datetime.timedelta(hours=24)
        
        # Generate time points in hours from reference_time
        time_range = np.linspace(0, 24, 1000)
        times = [self.reference_time + datetime.timedelta(hours=t) for t in time_range]
        
        # Plot individual intakes
        combined_caffeine = np.zeros(len(times))
        
        for idx, intake in enumerate(self.intakes):
            caffeine_values = [
                caffeine_level_at_time(
                    intake['start_time'],
                    intake['amount'],
                    intake['duration_hours'],
                    t
                )
                for t in times
            ]
            combined_caffeine += np.array(caffeine_values)
            
            color = COLORS[idx % len(COLORS)]
            self.ax.plot(time_range, caffeine_values, color=color, alpha=0.6, label=f"Intake {idx+1}")
        
        # Plot combined curve (bold, black)
        self.ax.plot(time_range, combined_caffeine, color='black', linewidth=2.5, label="Total Caffeine")
        
        # Labels and formatting
        self.ax.set_xlabel("Hours from reference time", fontsize=11)
        self.ax.set_ylabel("Caffeine Level (mg)", fontsize=11)
        self.ax.set_title("Caffeine Level Over Time", fontsize=12, fontweight='bold')
        self.ax.legend(loc='upper right', fontsize=9)
        self.ax.grid(True, alpha=0.3)
        self.ax.set_xlim(0, 24)
        self.ax.set_ylim(bottom=0)
        
        self.fig.tight_layout()
        self.canvas.draw()


if __name__ == "__main__":
    root = tk.Tk()
    app = CaffeineTrackerApp(root)
    root.mainloop()

