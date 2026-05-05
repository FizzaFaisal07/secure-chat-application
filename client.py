import socket
import threading
import json
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, simpledialog, ttk
import base64
import os
import time
import platform
import subprocess
from PIL import Image, ImageTk
import io

# Optional: OpenCV for Video Call
try:
    import cv2
    VIDEO_AVAILABLE = True
except ImportError:
    VIDEO_AVAILABLE = False
    print("OpenCV not available - video calling disabled")

# Optional: PyAudio for Voice
try:
    import pyaudio
    import wave
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("PyAudio not available - voice messages disabled")

# Configuration - Fixed Server IP (MUST MATCH SERVER IP)
SERVER_IP = '127.0.0.1'  # Changed to match server IP
PORT = 12345 # Changed to match server port
CHUNK = 1024
# Audio Format Settings
FORMAT = pyaudio.paInt16 if AUDIO_AVAILABLE else None
CHANNELS = 1
RATE = 44100

# Modern Color Scheme
COLORS = {
    "primary": "#2C3E50",
    "secondary": "#34495E", 
    "accent": "#3498DB",
    "success": "#2ECC71",
    "warning": "#F39C12",
    "danger": "#E74C3C",
    "light": "#ECF0F1",
    "dark": "#2C3E50",
    "text": "#2C3E50",
    "text_light": "#7F8C8D",
    "background": "#F5F7FA",
    "sidebar": "#2C3E50",
    "chat_bg": "#FFFFFF",
    "call_green": "#25D366",
    "call_red": "#FF3B30"
}

class ModernButton(tk.Button):
    def __init__(self, master=None, **kwargs):
        bg = kwargs.pop('bg', COLORS['accent'])
        fg = kwargs.pop('fg', 'white')
        font = kwargs.pop('font', ("Arial", 10, "bold"))
        relief = kwargs.pop('relief', 'flat')
        bd = kwargs.pop('bd', 0)
        padx = kwargs.pop('padx', 15)
        pady = kwargs.pop('pady', 8)
        
        super().__init__(master, bg=bg, fg=fg, font=font, relief=relief, bd=bd, 
                        padx=padx, pady=pady, cursor="hand2", **kwargs)
        
        self.original_color = self['bg']
        
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
    
    def on_enter(self, e):
        self.config(bg=self.darken_color(self['bg']))
    
    def on_leave(self, e):
        self.config(bg=self.original_color)
    
    def darken_color(self, color):
        r, g, b = self.winfo_rgb(color)
        r = max(0, r - 2000)
        g = max(0, g - 2000)
        b = max(0, b - 2000)
        return f"#{r:04x}{g:04x}{b:04x}"[0:7]

class ModernEntry(tk.Entry):
    def __init__(self, master=None, **kwargs):
        bg = kwargs.pop('bg', 'white')
        fg = kwargs.pop('fg', COLORS['text'])
        font = kwargs.pop('font', ("Arial", 11))
        relief = kwargs.pop('relief', 'flat')
        bd = kwargs.pop('bd', 2)
        highlightcolor = kwargs.pop('highlightcolor', COLORS['accent'])
        show = kwargs.pop('show', None)
        
        super().__init__(master, bg=bg, fg=fg, font=font, relief=relief, bd=bd,
                        highlightcolor=highlightcolor, highlightthickness=1, show=show, **kwargs)

class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Secure Chat Application")
        self.root.geometry("1200x800")
        self.root.configure(bg=COLORS['background'])
        self.root.minsize(1000, 700)
        
        try:
            self.root.iconbitmap(default='chat_icon.ico')
        except:
            pass
        
        self.client_socket = None
        self.username = ""
        self.is_connected = False
        self.authenticated = False
        
        # UI State
        self.tabs = {} 
        self.chat_widgets = {}
        
        # Call State
        self.active_call_window = None
        self.call_wait_window = None
        self.incoming_call_window = None
        self.in_call = False
        self.current_call_partner = None
        self.current_call_type = None
        self.audio_stream = None
        self.audio_p = None
        
        # Video State
        self.local_video_label = None
        self.remote_video_label = None
        self.video_capture = None
        self.video_stream_active = False
        self.audio_stream_active = False

        self.setup_login_screen()

    def setup_login_screen(self):
        # Clear any existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()
            
        # Reset state
        self.authenticated = False
        
        # Main container with gradient effect
        self.login_container = tk.Frame(self.root, bg=COLORS['primary'])
        self.login_container.pack(fill=tk.BOTH, expand=True)
        
        # Center frame
        self.login_frame = tk.Frame(self.login_container, bg='white', relief='flat', bd=0)
        self.login_frame.place(relx=0.5, rely=0.5, anchor='center', width=400, height=450)
        
        # Header with icon
        header_frame = tk.Frame(self.login_frame, bg='white')
        header_frame.pack(fill=tk.X, pady=(30, 20))
        
        # Icon placeholder
        icon_label = tk.Label(header_frame, text="🔐", font=("Arial", 40), bg='white', fg=COLORS['accent'])
        icon_label.pack()
        
        tk.Label(header_frame, text="Secure Chat Application", font=("Arial", 20, "bold"), 
                bg='white', fg=COLORS['text']).pack(pady=(10, 5))
        tk.Label(header_frame, text="Enter credentials to login", font=("Arial", 11), 
                bg='white', fg=COLORS['text_light']).pack()
        
        # Form container
        form_frame = tk.Frame(self.login_frame, bg='white')
        form_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=20)
        
        # Username
        tk.Label(form_frame, text="Username", font=("Arial", 10, "bold"), 
                bg='white', fg=COLORS['text'], anchor='w').pack(fill=tk.X, pady=(15, 5))
        self.username_entry = ModernEntry(form_frame)
        self.username_entry.pack(fill=tk.X, pady=(0, 10))
        self.username_entry.focus()  # Focus on username field
        self.username_entry.bind("<Return>", lambda e: self.password_entry.focus())
        
        # Password
        tk.Label(form_frame, text="Password", font=("Arial", 10, "bold"), 
                bg='white', fg=COLORS['text'], anchor='w').pack(fill=tk.X, pady=(5, 5))
        self.password_entry = ModernEntry(form_frame, show="•")
        self.password_entry.pack(fill=tk.X, pady=(0, 10))
        self.password_entry.bind("<Return>", lambda e: self.connect_to_server())
        
        # Show password checkbox
        self.show_password_var = tk.BooleanVar()
        
        checkbox_container = tk.Frame(form_frame, bg='white')
        checkbox_container.pack(fill=tk.X, pady=(5, 20))
        
        self.show_password_btn = ModernButton(
            checkbox_container,
            text="☐ Show password",
            command=self.toggle_password_checkbox,
            bg='white',
            fg=COLORS['text_light'],
            font=("Arial", 10),
            relief='flat',
            padx=0,
            pady=2
        )
        self.show_password_btn.pack(anchor='w')
        
        
        
        # Footer
        footer_frame = tk.Frame(self.login_frame, bg='white')
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=15)
        tk.Label(footer_frame, text=f"Press Enter to login • Server: {SERVER_IP}:{PORT}", font=("Arial", 9), 
                bg='white', fg=COLORS['text_light']).pack()

    def toggle_password_checkbox(self):
        """Toggle password visibility with custom checkbox"""
        current_state = self.show_password_var.get()
        new_state = not current_state
        self.show_password_var.set(new_state)
        
        if new_state:
            self.show_password_btn.config(text="☑ Show password", fg=COLORS['accent'])
            self.password_entry.config(show="")
        else:
            self.show_password_btn.config(text="☐ Show password", fg=COLORS['text_light'])
            self.password_entry.config(show="•")

    def connect_to_server(self):
        ip = SERVER_IP
        port = PORT
        self.username = self.username_entry.get().strip()
        password = self.password_entry.get()
        
        if not self.username:
            messagebox.showwarning("Input Error", "Please enter a username")
            return
            
        if not password:
            messagebox.showwarning("Input Error", "Please enter a password")
            return

        # Show connecting state
        self.connecting_label = tk.Label(self.login_frame, text="Connecting...", 
                                  font=("Arial", 10), bg='white', fg=COLORS['accent'])
        self.connecting_label.place(relx=0.5, rely=0.9, anchor='center')
        self.root.update()

        try:
            print(f"🔗 Attempting to connect to {ip}:{port}...")
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(10)
            self.client_socket.connect((ip, port))
            self.client_socket.settimeout(None)
            
            self.is_connected = True
            print("✅ Connected to server, sending credentials...")
            
            # Send login with credentials
            self.send_packet({
                "type": "LOGIN", 
                "name": self.username,
                "password": password
            })
            
            self.connecting_label.config(text="Authenticating...")
            self.root.update()
            
            # Start receiving messages in background
            threading.Thread(target=self.receive_messages, daemon=True).start()
            
        except socket.timeout:
            if hasattr(self, 'connecting_label'):
                self.connecting_label.destroy()
            messagebox.showerror("Connection Error", f"Connection timeout. Server may be offline.")
            self.is_connected = False
        except ConnectionRefusedError:
            if hasattr(self, 'connecting_label'):
                self.connecting_label.destroy()
            messagebox.showerror("Connection Error", f"Connection refused. Server may be offline or port {PORT} is blocked.")
            self.is_connected = False
        except Exception as e:
            if hasattr(self, 'connecting_label'):
                self.connecting_label.destroy()
            messagebox.showerror("Connection Error", f"Failed to connect to server {SERVER_IP}:{PORT}\nError: {e}")
            self.is_connected = False

    def send_packet(self, data):
        if self.client_socket and self.is_connected:
            try:
                json_str = json.dumps(data) + "\n"
                self.client_socket.send(json_str.encode('utf-8'))
                return True
            except Exception as e:
                print(f"Send error: {e}")
                self.is_connected = False
                if self.authenticated:
                    self.root.after(0, self.reset_to_login)
                return False
        return False

    def setup_main_interface(self):
        if hasattr(self, 'login_container'):
            self.login_container.destroy()
            
        if hasattr(self, 'connecting_label'):
            self.connecting_label.destroy()

        self.authenticated = True
        self.main_container = tk.Frame(self.root, bg=COLORS['background'])
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # --- Modern Sidebar ---
        self.sidebar = tk.Frame(self.main_container, width=280, bg=COLORS['sidebar'], padx=15, pady=20)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)
        
        # User info header
        user_header = tk.Frame(self.sidebar, bg=COLORS['sidebar'])
        user_header.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(user_header, text=f"👤 {self.username}", font=("Arial", 12, "bold"), 
                bg=COLORS['sidebar'], fg='white', anchor='w').pack(fill=tk.X)
        
        # Connection status
        self.connection_status = tk.Label(user_header, text=f"✅ Connected to Server", 
                                        font=("Arial", 9), bg=COLORS['sidebar'], 
                                        fg=COLORS['success'], anchor='w')
        self.connection_status.pack(fill=tk.X)
        
        # Online Users section
        users_frame = tk.Frame(self.sidebar, bg=COLORS['sidebar'])
        users_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(users_frame, text="Online Users", font=("Arial", 11, "bold"), 
                bg=COLORS['sidebar'], fg='white', anchor='w').pack(fill=tk.X)
        
        user_container = tk.Frame(users_frame, bg=COLORS['secondary'], relief='flat', bd=1)
        user_container.pack(fill=tk.X, pady=(8, 0))
        
        self.user_listbox = tk.Listbox(user_container, height=12, bg=COLORS['secondary'], 
                                      fg='white', selectbackground=COLORS['accent'],
                                      borderwidth=0, highlightthickness=0,
                                      font=("Arial", 10))
        self.user_listbox.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self.user_listbox.bind("<Double-Button-1>", self.on_user_double_click)
        
        # Groups section
        groups_frame = tk.Frame(self.sidebar, bg=COLORS['sidebar'])
        groups_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(groups_frame, text="My Groups", font=("Arial", 11, "bold"), 
                bg=COLORS['sidebar'], fg='white', anchor='w').pack(fill=tk.X)
        
        group_container = tk.Frame(groups_frame, bg=COLORS['secondary'], relief='flat', bd=1)
        group_container.pack(fill=tk.X, pady=(8, 0))
        
        self.group_listbox = tk.Listbox(group_container, height=8, bg=COLORS['secondary'], 
                                       fg='white', selectbackground=COLORS['accent'],
                                       borderwidth=0, highlightthickness=0,
                                       font=("Arial", 10))
        self.group_listbox.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self.group_listbox.bind("<Double-Button-1>", self.on_group_double_click)
        
        # Group actions
        action_frame = tk.Frame(self.sidebar, bg=COLORS['sidebar'])
        action_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        ModernButton(action_frame, text="➕ Create Group", command=self.create_group_dialog, 
                    bg=COLORS['success'], pady=6).pack(fill=tk.X, pady=2)
        ModernButton(action_frame, text="👥 Add Member", command=self.add_member_dialog, 
                    bg=COLORS['accent'], pady=6).pack(fill=tk.X, pady=2)
        ModernButton(action_frame, text="🚪 Leave Group", command=self.leave_group, 
                    bg=COLORS['danger'], pady=6).pack(fill=tk.X, pady=2)
        
        # --- Modern Chat Area ---
        chat_container = tk.Frame(self.main_container, bg=COLORS['background'])
        chat_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Custom styled notebook
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Custom.TNotebook", background=COLORS['background'], borderwidth=0)
        style.configure("Custom.TNotebook.Tab", 
                       padding=[20, 8], background=COLORS['light'], 
                       foreground=COLORS['text'], font=('Arial', 10, 'bold'))
        style.map("Custom.TNotebook.Tab", 
                 background=[('selected', COLORS['accent']), ('active', COLORS['accent'])],
                 foreground=[('selected', 'white'), ('active', 'white')])
        
        self.notebook = ttk.Notebook(chat_container, style="Custom.TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.create_chat_tab("Public", "🌍 Public Chat")
        
        # Start connection monitoring
        self.check_connection_status()

    def check_connection_status(self):
        """Periodically check connection status"""
        if not self.is_connected and self.authenticated:
            self.root.after(0, self.reset_to_login)
        elif self.authenticated:
            # Check every 30 seconds
            self.root.after(30000, self.check_connection_status)

    def create_chat_tab(self, chat_id, label):
        if chat_id in self.tabs:
            self.notebook.select(self.tabs[chat_id])
            return

        # Create tab frame
        frame = tk.Frame(self.notebook, bg=COLORS['chat_bg'])
        self.notebook.add(frame, text=label)
        self.tabs[chat_id] = frame

        # Header with Call Buttons (Only for Private Chats)
        if chat_id != "Public" and chat_id not in self.get_all_groups():
            header = tk.Frame(frame, bg=COLORS['light'], height=50, pady=10)
            header.pack(fill=tk.X, padx=15, pady=10)
            header.pack_propagate(False)
            
            tk.Label(header, text=f"💬 Chat with {chat_id}", font=("Arial", 12, "bold"), 
                    bg=COLORS['light'], fg=COLORS['text']).pack(side=tk.LEFT, padx=15)
            
            btn_container = tk.Frame(header, bg=COLORS['light'])
            btn_container.pack(side=tk.RIGHT, padx=15)
            
            ModernButton(btn_container, text="📹 Video Call", 
                        command=lambda: self.initiate_call(chat_id, "Video"),
                        bg=COLORS['accent'], font=("Arial", 9), padx=12, pady=5).pack(side=tk.RIGHT, padx=5)
            ModernButton(btn_container, text="📞 Audio Call", 
                        command=lambda: self.initiate_call(chat_id, "Audio"),
                        bg=COLORS['success'], font=("Arial", 9), padx=12, pady=5).pack(side=tk.RIGHT, padx=5)

        # Chat area with modern styling - UPDATED FOR PROPER LEFT/RIGHT ALIGNMENT
        chat_frame = tk.Frame(frame, bg=COLORS['chat_bg'])
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        # Create a frame that will contain both the chat area and scrollbar
        chat_container = tk.Frame(chat_frame, bg=COLORS['chat_bg'])
        chat_container.pack(fill=tk.BOTH, expand=True)
        
        # Create scrollbar
        scrollbar = tk.Scrollbar(chat_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create chat area with custom styling for left/right alignment
        chat_area = tk.Text(chat_container, state='disabled', height=20,
                          bg='white', fg=COLORS['text'], 
                          font=("Arial", 11), relief='flat', bd=1,
                          wrap=tk.WORD, yscrollcommand=scrollbar.set,
                          padx=10, pady=10)
        chat_area.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=chat_area.yview)
        
        # Configure text tags for different message alignments
        # SENT messages (self) - RIGHT aligned with blue background
        chat_area.tag_config('self', 
                           foreground='white', 
                           background=COLORS['accent'],
                           justify='right',
                           lmargin1=50,   # Left margin for wrapped text
                           lmargin2=50,   # Left margin for subsequent lines
                           rmargin=10,    # Right margin
                           relief='raised',
                           borderwidth=1,
                           spacing1=5,    # Space above
                           spacing3=5,    # Space below
                           selectbackground=COLORS['accent'])

        
        # RECEIVED messages (other) - LEFT aligned with light gray background
        chat_area.tag_config('other', 
                           foreground=COLORS['text'], 
                           background=COLORS['light'],
                           justify='left',
                           lmargin1=10,   # Left margin
                           lmargin2=10,   # Left margin for subsequent lines
                           rmargin=50,    # Right margin for wrapped text
                           relief='raised',
                           borderwidth=1,
                           spacing1=5,
                           spacing3=5,
                           selectbackground=COLORS['light'])
        
        # System messages - CENTER aligned
        chat_area.tag_config('system', 
                           foreground=COLORS['text_light'], 
                           font=("Arial", 10, "italic"), 
                           justify='center')
        
        # Timestamp for sent messages - RIGHT aligned
        chat_area.tag_config('timestamp_self', 
                           foreground=COLORS['text_light'], 
                           font=("Arial", 8),
                           justify='right')
        
        # Timestamp for received messages - LEFT aligned  
        chat_area.tag_config('timestamp_other', 
                           foreground=COLORS['text_light'], 
                           font=("Arial", 8),
                           justify='left')
        
        self.chat_widgets[chat_id] = chat_area

        # Modern input area
        input_frame = tk.Frame(frame, bg=COLORS['chat_bg'], height=60)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=15, pady=15)
        input_frame.pack_propagate(False)
        
        # Input container with shadow effect
        input_container = tk.Frame(input_frame, bg=COLORS['light'], relief='raised', bd=1)
        input_container.pack(fill=tk.BOTH, expand=True)
        
        entry = ModernEntry(input_container, font=("Arial", 11))
        entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        entry.bind("<Return>", lambda e: self.send_msg_from_tab(chat_id, entry))
        
        # Button container
        btn_frame = tk.Frame(input_container, bg=COLORS['light'])
        btn_frame.pack(side=tk.RIGHT, padx=5, pady=5)
        
        ModernButton(btn_frame, text="Send", command=lambda: self.send_msg_from_tab(chat_id, entry),
                    bg=COLORS['accent'], font=("Arial", 9), padx=12, pady=6).pack(side=tk.LEFT, padx=2)
        ModernButton(btn_frame, text="📎", command=lambda: self.send_file_from_tab(chat_id),
                    bg=COLORS['warning'], font=("Arial", 12), padx=8, pady=6).pack(side=tk.LEFT, padx=2)
        
        if AUDIO_AVAILABLE:
            ModernButton(btn_frame, text="🎤", command=lambda: self.send_voice_from_tab(chat_id),
                        bg=COLORS['danger'], font=("Arial", 12), padx=8, pady=6).pack(side=tk.LEFT, padx=2)

        self.notebook.select(frame)

    def send_msg_from_tab(self, chat_id, entry_widget):
        msg = entry_widget.get().strip()
        if not msg: return
        
        if chat_id == "Public":
            self.send_packet({"type": "PUBLIC_MSG", "msg": msg})
        elif chat_id in self.get_all_groups():
            self.send_packet({"type": "GROUP_MSG", "target": chat_id, "msg": msg})
        else:
            self.send_packet({"type": "PRIVATE_MSG", "target": chat_id, "msg": msg})
        entry_widget.delete(0, tk.END)

    def send_file_from_tab(self, chat_id):
        filepath = filedialog.askopenfilename(
            title="Select file to send",
            filetypes=[
                ("All files", "."),
                ("Images", ".png;.jpg;.jpeg;.gif"),
                ("Documents", ".pdf;.doc;.docx;.txt")
            ]
        )
        if not filepath: 
            return
            
        filename = os.path.basename(filepath)
        try:
            with open(filepath, "rb") as f:
                file_data = f.read()
                encoded = base64.b64encode(file_data).decode('utf-8')
                
            is_group = chat_id in self.get_all_groups()
            target = "All" if chat_id == "Public" else chat_id
            
            self.send_packet({
                "type": "FILE", 
                "filename": filename, 
                "data": encoded, 
                "target": target, 
                "is_group": is_group
            })
            
            # Show success message in chat
            self.append_to_tab(chat_id, f"File sent: {filename}", 'system')
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send file: {str(e)}")

    def send_voice_from_tab(self, chat_id):
        if not AUDIO_AVAILABLE:
            messagebox.showinfo("Voice Message", "PyAudio not found. Sending file instead.")
            self.send_file_from_tab(chat_id)
            return
        
        # Modern recording window
        status_window = tk.Toplevel(self.root)
        status_window.title("Recording Voice Message")
        status_window.geometry("300x150")
        status_window.configure(bg='white')
        status_window.resizable(False, False)
        
        # Center the window
        status_window.transient(self.root)
        status_window.grab_set()
        
        tk.Label(status_window, text="🎤 Recording...", font=("Arial", 14, "bold"), 
                bg='white', fg=COLORS['danger']).pack(pady=20)
        
        # Progress/countdown
        countdown_label = tk.Label(status_window, text="5 seconds remaining", 
                                  font=("Arial", 11), bg='white', fg=COLORS['text_light'])
        countdown_label.pack()
        
        progress = ttk.Progressbar(status_window, orient='horizontal', length=200, mode='determinate')
        progress.pack(pady=10)
        progress['maximum'] = 5
        progress['value'] = 0
        
        self.root.update()
        
        try:
            p = pyaudio.PyAudio()
            stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
            frames = []
            
            for i in range(0, int(RATE / CHUNK * 5)):
                data = stream.read(CHUNK)
                frames.append(data)
                # Update progress
                if i % (int(RATE / CHUNK)) == 0:
                    seconds = 4 - (i // int(RATE / CHUNK))
                    countdown_label.config(text=f"{seconds} seconds remaining")
                    progress['value'] = 5 - seconds
                    status_window.update()
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            status_window.destroy()
            
            # Save and send
            temp_filename = f"voice_sent_{int(time.time())}.wav"
            wf = wave.open(temp_filename, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
            wf.close()
            
            with open(temp_filename, "rb") as f:
                encoded = base64.b64encode(f.read()).decode('utf-8')
            
            is_group = chat_id in self.get_all_groups()
            target = "All" if chat_id == "Public" else chat_id
            self.send_packet({"type": "VOICE_MSG", "data": encoded, "target": target, "is_group": is_group})
            
            try: 
                os.remove(temp_filename)
            except: 
                pass
                
        except Exception as e:
            if 'status_window' in locals(): 
                status_window.destroy()
            messagebox.showerror("Error", f"Recording failed: {e}")

    def initiate_call(self, target, call_type):
        if self.in_call:
            messagebox.showinfo("Call in Progress", "You already have an active call.")
            return
            
        if self.send_packet({
            "type": f"{call_type.upper()}_CALL_REQUEST",
            "target": target
        }):
            self.show_calling_window(target, call_type)
        else:
            messagebox.showerror("Call Failed", "Failed to send call request")

    def show_calling_window(self, target, call_type):
        if self.call_wait_window:
            self.call_wait_window.destroy()
            
        self.call_wait_window = tk.Toplevel(self.root)
        self.call_wait_window.title(f"Calling {target}...")
        self.call_wait_window.geometry("350x200")
        self.call_wait_window.configure(bg='white')
        self.call_wait_window.resizable(False, False)
        self.call_wait_window.transient(self.root)
        self.call_wait_window.grab_set()
        
        icon = "📹" if call_type == "Video" else "📞"
        tk.Label(self.call_wait_window, text=icon, font=("Arial", 40), 
                bg='white', fg=COLORS['accent']).pack(pady=10)
        
        tk.Label(self.call_wait_window, text=f"Calling {target}...", 
                font=("Arial", 14, "bold"), bg='white', fg=COLORS['text']).pack()
        
        tk.Label(self.call_wait_window, text="Waiting for response...", 
                font=("Arial", 10), bg='white', fg=COLORS['text_light']).pack(pady=5)
        
        ModernButton(self.call_wait_window, text="Cancel Call", 
                    command=lambda: self.cancel_call(target), bg=COLORS['danger']).pack(pady=15)

    def cancel_call(self, target):
        if self.call_wait_window:
            self.call_wait_window.destroy()
            self.call_wait_window = None
        self.send_packet({"type": "CALL_ENDED", "target": target})

    def incoming_call_handler(self, caller, call_type):
        print(f"📞 Incoming {call_type} call from {caller}")
        
        # Close any existing incoming call window
        if self.incoming_call_window:
            try: 
                self.incoming_call_window.destroy()
            except: 
                pass

        self.incoming_call_window = tk.Toplevel(self.root)
        self.incoming_call_window.title("Incoming Call")
        self.incoming_call_window.geometry("400x300")
        self.incoming_call_window.configure(bg=COLORS['primary'])
        self.incoming_call_window.resizable(False, False)
        self.incoming_call_window.attributes('-topmost', True)
        self.incoming_call_window.transient(self.root)
        self.incoming_call_window.grab_set()
        
        # Make sure window is focused
        self.incoming_call_window.focus_force()
        
        icon = "📹" if call_type == "Video" else "📞"
        tk.Label(self.incoming_call_window, text=icon, font=("Arial", 50), 
                bg=COLORS['primary'], fg='white').pack(pady=20)
        
        tk.Label(self.incoming_call_window, text=f"Incoming {call_type} Call", 
                font=("Arial", 16, "bold"), bg=COLORS['primary'], fg='white').pack()
        
        tk.Label(self.incoming_call_window, text=f"From: {caller}", 
                font=("Arial", 12), bg=COLORS['primary'], fg=COLORS['light']).pack(pady=10)

        btn_frame = tk.Frame(self.incoming_call_window, bg=COLORS['primary'])
        btn_frame.pack(pady=30)

        ModernButton(btn_frame, text="ACCEPT", bg=COLORS['success'], 
                    font=("Arial", 12, "bold"), width=12,
                    command=lambda: self.accept_call(caller, call_type)).pack(side=tk.LEFT, padx=10)
        
        ModernButton(btn_frame, text="DECLINE", bg=COLORS['danger'], 
                    font=("Arial", 12, "bold"), width=12,
                    command=lambda: self.decline_call(caller)).pack(side=tk.LEFT, padx=10)

    def accept_call(self, caller, call_type):
        print(f"✅ Accepting call from {caller}")
        if self.incoming_call_window:
            self.incoming_call_window.destroy()
            self.incoming_call_window = None
        
        if self.send_packet({"type": "CALL_ACCEPTED", "target": caller, "call_type": call_type}):
            self.open_call_window(caller, call_type)
        else:
            messagebox.showerror("Call Error", "Failed to accept call")

    def decline_call(self, caller):
        print(f"❌ Declining call from {caller}")
        if self.incoming_call_window:
            self.incoming_call_window.destroy()
            self.incoming_call_window = None
        self.send_packet({"type": "CALL_DECLINED", "target": caller})

    def open_call_window(self, partner, call_type):
        print(f"🎬 Opening call window with {partner} for {call_type} call")
        
        # Close waiting window if exists
        if self.call_wait_window:
            self.call_wait_window.destroy()
            self.call_wait_window = None
        
        # Close existing call window
        if self.active_call_window:
            self.active_call_window.destroy()

        self.active_call_window = tk.Toplevel(self.root)
        self.active_call_window.title(f"{call_type} Call - {partner}")
        self.active_call_window.geometry("800x600")
        self.active_call_window.configure(bg='black')
        self.in_call = True
        self.current_call_partner = partner
        self.current_call_type = call_type
        self.video_stream_active = True
        self.audio_stream_active = True
        
        # Initialize media streams
        self.initialize_media_streams(partner, call_type)

        if call_type == "Video":
            self.setup_video_ui()
        else:
            self.setup_audio_ui(partner)

        # End call button
        ModernButton(self.active_call_window, text="End Call", command=self.close_call_window, 
                    bg=COLORS['danger'], font=("Arial", 12, "bold"), pady=10).pack(side=tk.BOTTOM, fill=tk.X, pady=10, padx=20)

    def initialize_media_streams(self, partner, call_type):
        # Initialize Audio
        if AUDIO_AVAILABLE and self.audio_stream_active:
            try:
                self.audio_p = pyaudio.PyAudio()
                # Output stream for receiving audio
                self.audio_output_stream = self.audio_p.open(
                    format=FORMAT, 
                    channels=CHANNELS, 
                    rate=RATE, 
                    output=True,
                    frames_per_buffer=CHUNK
                )
                # Input stream for sending audio
                self.audio_input_stream = self.audio_p.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK
                )
                # Start sending audio
                threading.Thread(target=self.stream_audio, args=(partner,), daemon=True).start()
                print(f"✅ Audio initialized for {call_type} call with {partner}")
            except Exception as e:
                print(f"❌ Audio Error: {e}")
                self.append_to_tab(partner, f"Audio not available: {e}", 'system')

        # Initialize Video
        if call_type == "Video" and VIDEO_AVAILABLE and self.video_stream_active:
            try:
                threading.Thread(target=self.stream_video, args=(partner,), daemon=True).start()
                print(f"✅ Video initialized for call with {partner}")
            except Exception as e:
                print(f"❌ Video Error: {e}")
                self.append_to_tab(partner, f"Video not available: {e}", 'system')

    def setup_video_ui(self):
        # Simple video UI - just show remote video
        video_frame = tk.Frame(self.active_call_window, bg='black')
        video_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Remote video (full screen)
        self.remote_video_label = tk.Label(video_frame, text="Waiting for video...", 
                                         bg="black", fg="white", font=("Arial", 16))
        self.remote_video_label.pack(fill=tk.BOTH, expand=True)
        
        # Status label at top
        status_frame = tk.Frame(video_frame, bg='black')
        status_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(status_frame, text=f"Video Call with {self.current_call_partner}", 
                font=("Arial", 12, "bold"), bg="black", fg="white").pack()

    def setup_audio_ui(self, partner):
        frame = tk.Frame(self.active_call_window, bg=COLORS['dark'])
        frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(frame, text="📞", font=("Arial", 80), bg=COLORS['dark'], fg=COLORS['accent']).pack(pady=50)
        tk.Label(frame, text="Audio Call Active", font=("Arial", 18, "bold"), 
                bg=COLORS['dark'], fg=COLORS['success']).pack()
        tk.Label(frame, text=f"Connected to {partner}", font=("Arial", 12), 
                bg=COLORS['dark'], fg=COLORS['light']).pack(pady=10)
        
        # Add audio status
        audio_status = "✅ Audio Enabled" if AUDIO_AVAILABLE else "❌ Audio Not Available"
        tk.Label(frame, text=audio_status, font=("Arial", 10), 
                bg=COLORS['dark'], fg=COLORS['light']).pack(pady=5)

    def stream_video(self, target):
        """Stream video to partner with robust error handling"""
        if not VIDEO_AVAILABLE:
            print("❌ OpenCV not available for video streaming")
            return
            
        try:
            # Try different camera backends to fix Windows camera issues
            for backend in [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]:
                cap = cv2.VideoCapture(0, backend)
                if cap.isOpened():
                    print(f"✅ Streaming camera opened with backend: {backend}")
                    break
                else:
                    if cap:
                        cap.release()
            
            if not cap.isOpened():
                print("❌ Camera not available for streaming")
                self.root.after(0, lambda: self.append_to_tab(target, "Camera not available for video call", 'system'))
                return
                
            # Set camera properties for better performance
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 15)  # Lower FPS for better performance
                
            print(f"🎥 Starting video stream to {target}")
            
            while self.video_stream_active and cap.isOpened():
                try:
                    ret, frame = cap.read()
                    if ret and self.video_stream_active:
                        # Resize frame for better performance
                        frame = cv2.resize(frame, (640, 480))
                        
                        # Encode frame
                        encoded, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                        if encoded:
                            b64_data = base64.b64encode(buffer).decode('utf-8')
                            
                            # Send video data
                            if not self.send_packet({
                                "type": "VIDEO_STREAM", 
                                "target": target, 
                                "data": b64_data
                            }):
                                print("❌ Failed to send video packet")
                                break
                        time.sleep(0.067)  # ~15 FPS
                    else:
                        print("❌ Failed to read frame from camera")
                        break
                        
                except Exception as e:
                    print(f"❌ Frame processing error: {e}")
                    break
                    
            cap.release()
            print(f"🎥 Video stream to {target} ended")
            
        except Exception as e:
            print(f"❌ Video streaming error: {e}")
            self.root.after(0, lambda: self.append_to_tab(target, "Video streaming error", 'system'))

    def stream_audio(self, target):
        """Stream audio to partner with error handling"""
        if not AUDIO_AVAILABLE:
            return
            
        try:
            while self.audio_stream_active:
                try:
                    data = self.audio_input_stream.read(CHUNK, exception_on_overflow=False)
                    b64_data = base64.b64encode(data).decode('utf-8')
                    if not self.send_packet({"type": "AUDIO_STREAM", "target": target, "data": b64_data}):
                        print("❌ Failed to send audio packet")
                        break
                except Exception as e:
                    print(f"❌ Error reading audio: {e}")
                    break
                    
        except Exception as e:
            print(f"❌ Mic Error: {e}")

    def close_call_window(self):
        """Properly close call window and cleanup resources"""
        print("🔚 Closing call window")
        self.in_call = False
        self.video_stream_active = False
        self.audio_stream_active = False
        
        # Send call ended notification
        if self.current_call_partner:
            self.send_packet({"type": "CALL_ENDED", "target": self.current_call_partner})
        
        # Stop video
        if hasattr(self, 'video_capture') and self.video_capture:
            self.video_capture.release()
            
        # Stop audio
        if hasattr(self, 'audio_input_stream'):
            try:
                self.audio_input_stream.stop_stream()
                self.audio_input_stream.close()
            except: 
                pass
        
        if hasattr(self, 'audio_output_stream'):
            try:
                self.audio_output_stream.stop_stream()
                self.audio_output_stream.close()
            except: 
                pass
        
        if hasattr(self, 'audio_p'):
            try:
                self.audio_p.terminate()
            except:
                pass
            
        if self.active_call_window:
            self.active_call_window.destroy()
            self.active_call_window = None
        
        self.current_call_partner = None
        self.current_call_type = None

    def receive_messages(self):
        """Receive messages from server with improved error handling"""
        buffer = ""
        while self.is_connected:
            try:
                # Increased buffer size for video streams
                data = self.client_socket.recv(65536)
                if not data: 
                    break
                buffer += data.decode('utf-8')
                while "\n" in buffer:
                    msg_str, buffer = buffer.split("\n", 1)
                    if msg_str.strip():
                        try: 
                            message_data = json.loads(msg_str)
                            self.process_message(message_data)
                        except json.JSONDecodeError as e:
                            print(f"❌ JSON Error: {e} - Data: {msg_str[:100]}...")
            except ConnectionResetError:
                print("❌ Server connection reset")
                break
            except Exception as e:
                print(f"❌ Connection Error: {e}")
                break
        
        if self.is_connected:
            self.root.after(0, self.reset_to_login)

    def process_message(self, data):
        """Process incoming messages with complete call handling"""
        msg_type = data.get("type")
        
        if msg_type == "AUTH_SUCCESS":
            # Authentication successful, setup main interface
            self.root.after(0, self.setup_main_interface)
            if hasattr(self, 'connecting_label'):
                self.connecting_label.destroy()
            return
            
        elif msg_type == "AUTH_ERROR":
            # Authentication failed
            self.root.after(0, lambda: messagebox.showerror("Authentication Failed", data['msg']))
            self.is_connected = False
            if self.client_socket:
                try:
                    self.client_socket.close()
                except:
                    pass
            if hasattr(self, 'connecting_label'):
                self.connecting_label.destroy()
            return
            
        elif msg_type == "AUTH_REQUIRED":
            # Server requires authentication
            self.root.after(0, lambda: messagebox.showwarning("Authentication Required", data['msg']))
            self.is_connected = False
            if self.client_socket:
                try:
                    self.client_socket.close()
                except:
                    pass
            if hasattr(self, 'connecting_label'):
                self.connecting_label.destroy()
            return
        
        # Only process these messages if authenticated and main interface is set up
        if not self.authenticated:
            return
            
        if msg_type == "CHAT":
            sender = data["from"]
            msg = data["msg"]
            mode = data["mode"]
            chat_id = data.get("chat_id", "Public")
            timestamp = time.strftime("%H:%M")
            
            # Determine if this is our own message or from someone else
            is_self = (sender == self.username)
            
            if mode == "Public":
                self.root.after(0, lambda: self.append_to_tab("Public", f"{msg}", 'self' if is_self else 'other', timestamp, is_self))
            else:
                self.root.after(0, lambda: self.append_to_tab(chat_id, f"{msg}", 'self' if is_self else 'other', timestamp, is_self))

        elif msg_type == "VIDEO_STREAM":
            if self.in_call and hasattr(self, 'remote_video_label'):
                try:
                    img_data = base64.b64decode(data["data"])
                    img_arr = Image.open(io.BytesIO(img_data))
                    imgtk = ImageTk.PhotoImage(image=img_arr)
                    self.root.after(0, lambda: self.update_remote_video_ui(imgtk))
                except Exception as e:
                    print(f"❌ Video stream processing error: {e}")

        elif msg_type == "AUDIO_STREAM":
            if self.in_call and hasattr(self, 'audio_output_stream'):
                try:
                    audio_data = base64.b64decode(data["data"])
                    self.audio_output_stream.write(audio_data)
                except Exception as e:
                    print(f"❌ Audio stream error: {e}")

        elif msg_type == "USER_LIST":
            self.root.after(0, lambda: self.update_list(self.user_listbox, data["users"]))
        
        elif msg_type == "GROUP_LIST":
            self.root.after(0, lambda: self.update_list(self.group_listbox, data["groups"]))

        elif msg_type == "SERVER":
            self.root.after(0, lambda: self.append_to_tab("Public", f"{data['msg']}", 'system'))

        elif msg_type in ["FILE_RX", "VOICE_RX"]:
            sender = data["from"]
            filename = data["filename"]
            chat_id = data.get("chat_id", "Public")
            content = base64.b64decode(data["data"])
            
            # Generate unique filename with timestamp
            timestamp = int(time.time())
            save_name = f"Rx_{timestamp}_{filename}"
            
            try:
                with open(save_name, "wb") as f: 
                    f.write(content)
                
                # Determine if this is our own file or from someone else
                is_self = (sender == self.username)
                
                if msg_type == "VOICE_RX":
                    self.root.after(0, lambda: self.append_voice_button(chat_id, f"Voice Note from {sender}", save_name, is_self))
                else:
                    # Check if it's an image file
                    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff']
                    is_image = any(filename.lower().endswith(ext) for ext in image_extensions)
                    
                    if is_image:
                        self.root.after(0, lambda: self.append_image_button(chat_id, f"Image from {sender}", save_name, is_self))
                    else:
                        self.root.after(0, lambda: self.append_file_button(chat_id, f"File: {filename} from {sender}", save_name, is_self))
                        
            except Exception as e:
                print(f"❌ Error saving file: {e}")
                self.root.after(0, lambda: self.append_to_tab(chat_id, f"Error saving file: {filename}", 'system'))

        # --- CALL HANDLING ---
        elif msg_type == "VIDEO_CALL_REQUEST":
            print("📹 Received video call request")
            self.root.after(0, lambda: self.incoming_call_handler(data["from"], "Video"))
        elif msg_type == "AUDIO_CALL_REQUEST":
            print("📞 Received audio call request")
            self.root.after(0, lambda: self.incoming_call_handler(data["from"], "Audio"))
        elif msg_type == "CALL_ACCEPTED":
            print("✅ Call accepted by other party")
            if self.call_wait_window:
                self.root.after(0, self.call_wait_window.destroy)
            self.root.after(0, lambda: self.open_call_window(data["from"], data["call_type"]))
        elif msg_type == "CALL_DECLINED":
            print("❌ Call declined by other party")
            if self.call_wait_window: 
                self.root.after(0, self.call_wait_window.destroy)
            self.root.after(0, lambda: messagebox.showinfo("Call Declined", f"{data['from']} declined your call."))
        elif msg_type == "CALL_FAILED":
            print("❌ Call failed")
            if self.call_wait_window: 
                self.root.after(0, self.call_wait_window.destroy)
            self.root.after(0, lambda: messagebox.showerror("Call Failed", data["msg"]))
        elif msg_type == "CALL_ENDED":  # Handle call ended from other party
            print("📞 Call ended by other party")
            if self.in_call:
                self.root.after(0, self.close_call_window)
                self.root.after(0, lambda: messagebox.showinfo("Call Ended", f"{data['from']} ended the call."))
        elif msg_type == "CALL_SENT":
            # Call request was successfully sent to the recipient
            print(f"✅ Call request sent to {data['target']}")

    def update_remote_video_ui(self, imgtk):
        """Update remote video display in main thread"""
        if (hasattr(self, 'remote_video_label') and self.in_call and 
            self.remote_video_label.winfo_exists()):
            try:
                self.remote_video_label.imgtk = imgtk
                self.remote_video_label.configure(image=imgtk, text="")
            except Exception as e:
                print(f"❌ Remote video UI error: {e}")

    # --- UPDATED UI HELPER METHODS FOR LEFT/RIGHT ALIGNMENT ---
    def append_to_tab(self, chat_id, text, tag=None, timestamp=None, is_self=False):
        """Append message to chat tab with proper left/right alignment"""
        if chat_id not in self.tabs: 
            display_name = f"💬 {chat_id}" if chat_id != "Public" else "🌍 Public Chat"
            self.create_chat_tab(chat_id, display_name)
        
        widget = self.chat_widgets[chat_id]
        widget.config(state='normal')
        
        # Use appropriate tag based on who sent the message
        if tag is None:
            tag = 'self' if is_self else 'other'
        
        # Add timestamp if provided
        if timestamp:
            timestamp_tag = 'timestamp_self' if is_self else 'timestamp_other'
            widget.insert(tk.END, f"[{timestamp}] ", timestamp_tag)
        
        # Add the message with proper alignment
        widget.insert(tk.END, text + "\n", tag)
        widget.see(tk.END)
        widget.config(state='disabled')

    def update_list(self, listbox, items):
        listbox.delete(0, tk.END)
        for item in items:
            if item != self.username: 
                # Display just the username, not "Video Call - username"
                listbox.insert(tk.END, item)

    def on_user_double_click(self, event):
        selection = self.user_listbox.curselection()
        if selection:
            user = self.user_listbox.get(selection[0])
            self.create_chat_tab(user, f"💬 {user}")

    def on_group_double_click(self, event):
        selection = self.group_listbox.curselection()
        if selection:
            group = self.group_listbox.get(selection[0])
            self.create_chat_tab(group, f"👥 {group}")

    def create_group_dialog(self):
        name = simpledialog.askstring("Create Group", "Enter Group Name:", 
                                     parent=self.root)
        if name: 
            self.send_packet({"type": "CREATE_GROUP", "group_name": name})

    def add_member_dialog(self):
        selection = self.group_listbox.curselection()
        if not selection: 
            messagebox.showwarning("Select Group", "Please select a group first.")
            return
        
        group = self.group_listbox.get(selection[0])
        member = simpledialog.askstring("Add Member", "Enter username:", 
                                       parent=self.root)
        if member: 
            self.send_packet({"type": "ADD_MEMBER", "group_name": group, "member_name": member})

    def leave_group(self):
        selection = self.group_listbox.curselection()
        if selection:
            group = self.group_listbox.get(selection[0])
            confirm = messagebox.askyesno("Leave Group", f"Are you sure you want to leave '{group}'?")
            if confirm:
                self.send_packet({"type": "LEAVE_GROUP", "group_name": group})

    def get_all_groups(self):
        return self.group_listbox.get(0, tk.END)

    def reset_to_login(self):
        self.is_connected = False
        self.authenticated = False
        if hasattr(self, 'main_container'): 
            self.main_container.destroy()
        if self.client_socket: 
            try:
                self.client_socket.close()
            except:
                pass
        self.setup_login_screen()

    # File handling methods
    def play_voice_note(self, filepath):
        if AUDIO_AVAILABLE:
            try:
                wf = wave.open(filepath, 'rb')
                p = pyaudio.PyAudio()
                stream = p.open(format=p.get_format_from_width(wf.getsampwidth()), 
                               channels=wf.getnchannels(), rate=wf.getframerate(), output=True)
                data = wf.readframes(CHUNK)
                while data:
                    stream.write(data)
                    data = wf.readframes(CHUNK)
                stream.stop_stream()
                stream.close()
                p.terminate()
                return
            except: 
                pass
        try:
            if platform.system() == 'Windows': 
                os.startfile(filepath)
            elif platform.system() == 'Darwin': 
                subprocess.call(('open', filepath))
            else: 
                subprocess.call(('xdg-open', filepath))
        except: 
            messagebox.showerror("Error", "Could not play audio.")

    def open_image_file(self, filepath):
        """Open image file in default viewer or show in a new window"""
        try:
            if platform.system() == 'Windows': 
                os.startfile(filepath)
            elif platform.system() == 'Darwin': 
                subprocess.call(('open', filepath))
            else: 
                subprocess.call(('xdg-open', filepath))
        except:
            try:
                img_window = tk.Toplevel(self.root)
                img_window.title(f"Image: {os.path.basename(filepath)}")
                img_window.geometry("600x500")
                
                img = Image.open(filepath)
                if img.width > 800 or img.height > 600:
                    img.thumbnail((800, 600), Image.Resampling.LANCZOS)
                
                img_tk = ImageTk.PhotoImage(img)
                label = tk.Label(img_window, image=img_tk)
                label.image = img_tk
                label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                
                ModernButton(img_window, text="Close", command=img_window.destroy,
                            bg=COLORS['danger']).pack(pady=10)
            except Exception as e:
                messagebox.showerror("Error", f"Cannot open image: {e}")

    def open_any_file(self, filepath):
        """Open any file with default system application"""
        try:
            if platform.system() == 'Windows': 
                os.startfile(filepath)
            elif platform.system() == 'Darwin': 
                subprocess.call(('open', filepath))
            else: 
                subprocess.call(('xdg-open', filepath))
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open file: {e}")

    def append_image_button(self, chat_id, text, filename, is_self=False):
        if chat_id not in self.tabs: 
            self.create_chat_tab(chat_id, chat_id)
        
        widget = self.chat_widgets[chat_id]
        widget.config(state='normal')
        
        timestamp = time.strftime("%H:%M")
        timestamp_tag = 'timestamp_self' if is_self else 'timestamp_other'
        widget.insert(tk.END, f"[{timestamp}] ", timestamp_tag)
        
        btn = ModernButton(widget, text="🖼 View Image", 
                          command=lambda: self.open_image_file(filename),
                          bg=COLORS['accent'], font=("Arial", 8), padx=8, pady=2)
        
        # Use proper alignment tags
        if is_self:
            widget.insert(tk.END, "\n", 'self')
            widget.window_create(tk.END, window=btn)
            widget.insert(tk.END, f" {text}\n", 'self')
        else:
            widget.insert(tk.END, f"{text} ", 'other')
            widget.window_create(tk.END, window=btn)
            widget.insert(tk.END, "\n", 'other')
            
        widget.see(tk.END)
        widget.config(state='disabled')

    def append_file_button(self, chat_id, text, filename, is_self=False):
        if chat_id not in self.tabs: 
            self.create_chat_tab(chat_id, chat_id)
        
        widget = self.chat_widgets[chat_id]
        widget.config(state='normal')
        
        timestamp = time.strftime("%H:%M")
        timestamp_tag = 'timestamp_self' if is_self else 'timestamp_other'
        widget.insert(tk.END, f"[{timestamp}] ", timestamp_tag)
        
        btn = ModernButton(widget, text="📂 Open File", 
                          command=lambda: self.open_any_file(filename),
                          bg=COLORS['success'], font=("Arial", 8), padx=8, pady=2)
        
        if is_self:
            widget.insert(tk.END, "\n", 'self')
            widget.window_create(tk.END, window=btn)
            widget.insert(tk.END, f" {text}\n", 'self')
        else:
            widget.insert(tk.END, f"{text} ", 'other')
            widget.window_create(tk.END, window=btn)
            widget.insert(tk.END, "\n", 'other')
            
        widget.see(tk.END)
        widget.config(state='disabled')

    def append_voice_button(self, chat_id, text, filename, is_self=False):
        if chat_id not in self.tabs: 
            self.create_chat_tab(chat_id, chat_id)
        
        widget = self.chat_widgets[chat_id]
        widget.config(state='normal')
        
        timestamp = time.strftime("%H:%M")
        timestamp_tag = 'timestamp_self' if is_self else 'timestamp_other'
        widget.insert(tk.END, f"[{timestamp}] ", timestamp_tag)
        
        btn = ModernButton(widget, text="▶ Play", command=lambda: self.play_voice_note(filename), 
                          bg=COLORS['accent'], font=("Arial", 8), padx=8, pady=2)
        
        if is_self:
            widget.insert(tk.END, "\n", 'self')
            widget.window_create(tk.END, window=btn)
            widget.insert(tk.END, f" {text}\n", 'self')
        else:
            widget.insert(tk.END, f"{text} ", 'other')
            widget.window_create(tk.END, window=btn)
            widget.insert(tk.END, "\n", 'other')
            
        widget.see(tk.END)
        widget.config(state='disabled')

if __name__== "__main__":
    root = tk.Tk()
    client = ChatClient(root)
    root.mainloop()