import socket
import threading
import os
import json
import time
import base64

# Configuration - Bind to specific IP (REMOVED SPACES)
host = '0.0.0.0'  # Listen on all network interfaces
port = int(os.environ.get('PORT', 5000))

# Predefined users (username: password)
AUTHENTICATED_USERS = {
    "alice": "12345",
    "bob": "456789", 
    "charlie": "7891011",
    "diana": "10111213",
    "eve": "11213141"
}

# Track login attempts for rate limiting
login_attempts = {}
MAX_LOGIN_ATTEMPTS = 3
LOCKOUT_TIME = 300  # 5 minutes in seconds

# Global State with thread locks
clients_lock = threading.Lock()
clients = {}       # {username: client_socket}
addresses = {}     # {client_socket: (username, address)}
groups = {}        # {group_name: [member_username1, member_username2, ...]}
group_admins = {}  # {group_name: admin_username}

def get_local_ip():
    """Helper to find the local IP address to show the user."""
    return '192.168.137.242'  # Removed space before IP

def is_user_locked_out(client_ip):
    """Check if an IP is temporarily locked out due to failed attempts"""
    if client_ip in login_attempts:
        attempts, first_attempt_time = login_attempts[client_ip]
        if attempts >= MAX_LOGIN_ATTEMPTS:
            if time.time() - first_attempt_time < LOCKOUT_TIME:
                return True
            else:
                # Reset attempts after lockout period
                del login_attempts[client_ip]
    return False

def record_failed_attempt(client_ip):
    """Record a failed login attempt"""
    current_time = time.time()
    if client_ip in login_attempts:
        attempts, first_attempt_time = login_attempts[client_ip]
        login_attempts[client_ip] = (attempts + 1, first_attempt_time)
    else:
        login_attempts[client_ip] = (1, current_time)

def record_successful_login(client_ip):
    """Clear failed attempts on successful login"""
    if client_ip in login_attempts:
        del login_attempts[client_ip]

def authenticate_user(username, password, client_ip):
    """Authenticate user credentials"""
    # Check if IP is locked out
    if is_user_locked_out(client_ip):
        return False, "Too many failed login attempts. Please try again in 5 minutes."
    
    # Check if username exists
    if username not in AUTHENTICATED_USERS:
        record_failed_attempt(client_ip)
        return False, "Invalid username or password."
    
    # Check if password matches
    if AUTHENTICATED_USERS[username] != password:
        record_failed_attempt(client_ip)
        return False, "Invalid username or password."
    
    # Check if user is already logged in
    with clients_lock:
        if username in clients:
            return False, "User is already logged in from another device."
    
    # Success
    record_successful_login(client_ip)
    return True, "Authentication successful."

def handle_client(client_socket, client_address):
    user_name = ""
    buffer = ""
    client_ip = client_address[0]
    
    try:
        # Give client 30 seconds to authenticate
        client_socket.settimeout(30.0)
        
        while True:
            try:
                # Increased buffer size for video streams
                data = client_socket.recv(65536)
                if not data:
                    print(f"[CLOSED] Client {client_ip} closed connection")
                    break
                
                buffer += data.decode('utf-8')
                
                while "\n" in buffer:
                    msg_str, buffer = buffer.split("\n", 1)
                    if not msg_str.strip(): 
                        continue
                    
                    try:
                        message_data = json.loads(msg_str)
                    except json.JSONDecodeError as e:
                        print(f"[ERROR] Invalid JSON from {client_ip}: {e}")
                        continue

                    msg_type = message_data.get("type")
                    
                    # --- AUTHENTICATION ---
                    if msg_type == "LOGIN":
                        if user_name:  # Already authenticated
                            continue
                            
                        username = message_data.get("name", "").strip()
                        password = message_data.get("password", "")
                        
                        if not username or not password:
                            send_json(client_socket, {"type": "AUTH_ERROR", "msg": "Username and password required."})
                            continue
                        
                        # Authenticate user
                        auth_success, auth_message = authenticate_user(username, password, client_ip)
                        
                        if auth_success:
                            user_name = username
                            with clients_lock:
                                clients[user_name] = client_socket
                                addresses[client_socket] = (user_name, client_address)
                            
                            print(f"[NEW CONNECTION] {user_name} connected from {client_ip}.")
                            
                            # Send success message
                            send_json(client_socket, {
                                "type": "AUTH_SUCCESS", 
                                "msg": f"Welcome, {user_name}!",
                                "encryption_key": "dummy_key_for_compatibility"
                            })
                            broadcast_user_list()
                            send_group_list(user_name)
                            
                            # Reset timeout after authentication
                            client_socket.settimeout(None)
                        else:
                            send_json(client_socket, {"type": "AUTH_ERROR", "msg": auth_message})
                            if is_user_locked_out(client_ip):
                                print(f"[LOCKOUT] IP {client_ip} temporarily locked out")
                                break

                    # All other message types require authentication
                    elif not user_name:
                        send_json(client_socket, {"type": "AUTH_REQUIRED", "msg": "Please login first."})
                        continue

                    # --- MESSAGING ---
                    elif msg_type == "PUBLIC_MSG":
                        # Broadcast to all INCLUDING the sender (for consistent display)
                        print(f"[PUBLIC] {user_name}: {message_data['msg'][:50]}...")
                        broadcast_message(user_name, message_data["msg"])
                        
                    elif msg_type == "PRIVATE_MSG":
                        target = message_data["target"]
                        content = message_data["msg"]
                        print(f"[PRIVATE] {user_name} -> {target}: {content[:50]}...")
                        send_private_message(user_name, target, content)
                    
                    elif msg_type == "GROUP_MSG":
                        group_name = message_data["target"]
                        content = message_data["msg"]
                        print(f"[GROUP] {user_name} -> {group_name}: {content[:50]}...")
                        send_group_message(user_name, group_name, content)

                    elif msg_type == "VOICE_MSG":
                        target = message_data["target"]
                        is_group = message_data.get("is_group", False)
                        data_b64 = message_data["data"]
                        
                        print(f"[VOICE] {user_name} sent voice message to {target}")
                        if is_group:
                            send_group_file(user_name, target, "voice_note.wav", data_b64, is_voice=True)
                        else:
                            send_private_file(user_name, target, "voice_note.wav", data_b64, is_voice=True)
                    
                    # --- STREAMING RELAY ---
                    elif msg_type in ["VIDEO_STREAM", "AUDIO_STREAM"]:
                        target = message_data["target"]
                        with clients_lock:
                            if target in clients and target != user_name:  # Prevent sending to self
                                try:
                                    # Forward stream data directly without processing
                                    send_json(clients[target], message_data)
                                except Exception as e:
                                    print(f"[STREAM ERROR] Failed to send to {target}: {e}")
                                    # Remove dead client
                                    if target in clients:
                                        del clients[target]
                            else:
                                # Target might have disconnected
                                print(f"[STREAM] Target {target} not found for {msg_type}")

                    # --- FILE SHARING ---
                    elif msg_type == "FILE":
                        target = message_data["target"]
                        filename = message_data["filename"]
                        file_data = message_data["data"]
                        is_group = message_data.get("is_group", False)

                        print(f"[FILE] {user_name} sent file to {target}: {filename}")
                        if is_group:
                            send_group_file(user_name, target, filename, file_data)
                        elif target == "All":
                            broadcast_file(user_name, filename, file_data)
                        else:
                            send_private_file(user_name, target, filename, file_data)

                    # --- GROUP MANAGEMENT ---
                    elif msg_type == "CREATE_GROUP":
                        group_name = message_data["group_name"]
                        if group_name in groups:
                            send_json(client_socket, {"type": "ERROR", "msg": "Group already exists."})
                        else:
                            groups[group_name] = [user_name]
                            group_admins[group_name] = user_name
                            send_group_list(user_name)
                            send_json(client_socket, {"type": "SERVER", "msg": f"Group '{group_name}' created."})
                            print(f"[GROUP] {user_name} created group '{group_name}'")

                    elif msg_type == "ADD_MEMBER":
                        group_name = message_data["group_name"]
                        new_member = message_data["member_name"]
                        
                        if group_name in groups and group_admins.get(group_name) == user_name:
                            if new_member in get_connected_users():
                                if new_member not in groups[group_name]:
                                    groups[group_name].append(new_member)
                                    send_group_list(new_member)
                                    send_group_message("System", group_name, f"{user_name} added {new_member}")
                                    print(f"[GROUP] {user_name} added {new_member} to {group_name}")
                                else:
                                    send_json(client_socket, {"type": "ERROR", "msg": "User already in group."})
                            else:
                                send_json(client_socket, {"type": "ERROR", "msg": "User not connected."})
                        else:
                            send_json(client_socket, {"type": "ERROR", "msg": "Only group admin can add members."})

                    elif msg_type == "LEAVE_GROUP":
                        group_name = message_data["group_name"]
                        if group_name in groups and user_name in groups[group_name]:
                            groups[group_name].remove(user_name)
                            send_group_list(user_name)
                            send_group_message("System", group_name, f"{user_name} left the group.")
                            print(f"[GROUP] {user_name} left {group_name}")
                            if not groups[group_name]:
                                del groups[group_name]
                                if group_name in group_admins:
                                    del group_admins[group_name]

                    # --- CALLING FEATURES ---
                    elif msg_type in ["VIDEO_CALL_REQUEST", "AUDIO_CALL_REQUEST"]:
                        target = message_data["target"]
                        call_type = "Video" if "VIDEO" in msg_type else "Audio"
                        with clients_lock:
                            if target in clients and target != user_name:  # Prevent calling yourself
                                print(f"📞 [CALL] {user_name} calling {target} ({call_type})")
                                # Send call request to target
                                if send_json(clients[target], {
                                    "type": msg_type, 
                                    "from": user_name
                                }):
                                    # Send confirmation to caller
                                    send_json(client_socket, {
                                        "type": "CALL_SENT",
                                        "target": target,
                                        "call_type": call_type
                                    })
                                    print(f"✅ Call request sent to {target}")
                                else:
                                    send_json(client_socket, {
                                        "type": "CALL_FAILED", 
                                        "msg": f"Failed to send call to {target}"
                                    })
                            else:
                                error_msg = "User not online." if target not in clients else "Cannot call yourself."
                                send_json(client_socket, {
                                    "type": "CALL_FAILED", 
                                    "msg": error_msg
                                })

                    elif msg_type in ["CALL_ACCEPTED", "CALL_DECLINED"]:
                        target = message_data["target"]
                        call_type = message_data.get("call_type", "Video")
                        with clients_lock:
                            if target in clients:
                                if send_json(clients[target], {
                                    "type": msg_type,
                                    "from": user_name,
                                    "call_type": call_type
                                }):
                                    action = "accepted" if "ACCEPTED" in msg_type else "declined"
                                    print(f"📞 [CALL] {user_name} {action} {target}'s {call_type} call")
                                else:
                                    print(f"❌ Failed to send call response to {target}")

                    # --- CALL ENDED ---
                    elif msg_type == "CALL_ENDED":
                        target = message_data.get("target")
                        with clients_lock:
                            if target in clients:
                                if send_json(clients[target], {
                                    "type": "CALL_ENDED",
                                    "from": user_name
                                }):
                                    print(f"📞 [CALL] {user_name} ended call with {target}")
                                else:
                                    print(f"❌ Failed to send call end to {target}")

            except socket.timeout:
                if not user_name:
                    send_json(client_socket, {"type": "AUTH_ERROR", "msg": "Authentication timeout. Please reconnect."})
                    break
            except ConnectionResetError:
                print(f"[CONNECTION RESET] {user_name if user_name else 'Unknown'} disconnected abruptly")
                break
            except Exception as e:
                print(f"[ERROR] {user_name if user_name else 'Unknown'}: {e}")
                break

    except Exception as e:
        print(f"[CRITICAL ERROR] {user_name if user_name else 'Unknown'}: {e}")
    finally:
        cleanup_client(user_name, client_socket)

def cleanup_client(user_name, sock):
    with clients_lock:
        if user_name in clients:
            del clients[user_name]
        if sock in addresses:
            del addresses[sock]
    
    try:
        sock.close()
    except:
        pass
    
    if user_name:  # Only broadcast if user was authenticated
        broadcast_user_list()
        print(f"[DISCONNECT] {user_name} disconnected. Active users: {len(clients)}")

def send_json(sock, data):
    try:
        json_str = json.dumps(data) + "\n"
        sock.send(json_str.encode('utf-8'))
        return True
    except (BrokenPipeError, ConnectionResetError, OSError):
        # Socket is closed, will be cleaned up in next iteration
        return False
    except Exception as e:
        print(f"[SEND ERROR] {e}")
        return False

def send_json_to_user(username, data):
    """Safely send JSON to a specific user"""
    with clients_lock:
        if username in clients:
            return send_json(clients[username], data)
    return False

def get_connected_users():
    """Get list of connected users in a thread-safe way"""
    with clients_lock:
        return list(clients.keys())

def broadcast_user_list():
    users = get_connected_users()
    msg = {"type": "USER_LIST", "users": users}
    
    with clients_lock:
        sockets_to_remove = []
        for username, sock in list(clients.items()):
            if not send_json(sock, msg):
                sockets_to_remove.append(username)
        
        # Clean up dead connections
        for username in sockets_to_remove:
            if username in clients:
                del clients[username]
                print(f"[CLEANUP] Removed dead connection: {username}")

def send_group_list(user_name):
    if user_name not in get_connected_users(): 
        return
    
    my_groups = []
    for g_name, members in groups.items():
        if user_name in members:
            my_groups.append(g_name)
    msg = {"type": "GROUP_LIST", "groups": my_groups}
    send_json_to_user(user_name, msg)

def broadcast_message(sender, content):
    msg = {"type": "CHAT", "from": sender, "msg": content, "mode": "Public", "chat_id": "Public"}
    
    with clients_lock:
        sockets_to_remove = []
        for username, sock in list(clients.items()):
            if not send_json(sock, msg):
                sockets_to_remove.append(username)
        
        # Clean up dead connections
        for username in sockets_to_remove:
            if username in clients:
                del clients[username]

def send_private_message(sender, target, content):
    # Send to target
    if not send_json_to_user(target, {
        "type": "CHAT", 
        "from": sender, 
        "msg": content, 
        "mode": "Private", 
        "chat_id": sender
    }):
        print(f"[PRIVATE MSG FAILED] Target {target} not available")
    
    # Send echo back to sender (so both parties see the message)
    send_json_to_user(sender, {
        "type": "CHAT", 
        "from": sender, 
        "msg": content, 
        "mode": "Private", 
        "chat_id": target
    })

def send_group_message(sender, group_name, content):
    if group_name not in groups: 
        return
    
    msg = {
        "type": "CHAT", 
        "from": sender, 
        "msg": content, 
        "mode": "Group", 
        "chat_id": group_name
    }
    
    for member in groups[group_name]:
        send_json_to_user(member, msg)

def broadcast_file(sender, filename, filedata):
    msg = {
        "type": "FILE_RX", 
        "from": sender, 
        "filename": filename, 
        "data": filedata, 
        "mode": "Public",
        "chat_id": "Public"
    }
    
    with clients_lock:
        sockets_to_remove = []
        for username, sock in list(clients.items()):
            if not send_json(sock, msg):
                sockets_to_remove.append(username)
        
        # Clean up dead connections
        for username in sockets_to_remove:
            if username in clients:
                del clients[username]

def send_private_file(sender, target, filename, filedata, is_voice=False):
    msg_type = "VOICE_RX" if is_voice else "FILE_RX"
    
    # Send to target
    send_json_to_user(target, {
        "type": msg_type, 
        "from": sender, 
        "filename": filename, 
        "data": filedata, 
        "mode": "Private", 
        "chat_id": sender
    })
    
    # Send echo back to sender
    send_json_to_user(sender, {
        "type": msg_type, 
        "from": sender, 
        "filename": filename, 
        "data": filedata, 
        "mode": "Private", 
        "chat_id": target
    })

def send_group_file(sender, group_name, filename, filedata, is_voice=False):
    if group_name not in groups: 
        return
    
    msg_type = "VOICE_RX" if is_voice else "FILE_RX"
    msg = {
        "type": msg_type, 
        "from": sender, 
        "filename": filename, 
        "data": filedata, 
        "mode": "Group", 
        "chat_id": group_name
    }
    
    for member in groups[group_name]:
        send_json_to_user(member, msg)

def start_server():
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Allow socket reuse
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(5)  # Increased backlog
        local_ip = get_local_ip()
        print(f"--------------------------------------------------")
        print(f"[LISTENING] Server is running on {HOST}:{PORT}")
        print(f"[CONNECT INFO] Clients will automatically connect to: {HOST}")
        print(f"[AUTHENTICATION] Server requires login with predefined credentials")
        print(f"[VIDEO CALLING] WhatsApp-style video calling enabled")
        print(f"[THREAD SAFETY] Thread-safe operations implemented")
        print(f"--------------------------------------------------")
        print(f"[AVAILABLE USERS]")
        for username in AUTHENTICATED_USERS.keys():
            print(f"  - {username}")
        print(f"--------------------------------------------------")
        
        while True:
            try:
                conn, addr = server.accept()
                print(f"[INCOMING] Connection from {addr[0]}:{addr[1]}")
                thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
                thread.start()
                print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")
            except Exception as e:
                print(f"[ACCEPT ERROR] {e}")
            
    except OSError as e:
        if e.errno == 10048:
            print(f"[ERROR] Port {PORT} is already in use!")
            print("Please wait 10 seconds for the port to be released, or:")
            print("1. Kill the existing process using the port, or")
            print("2. Change the PORT number in both client.py and server.py")
            print("3. Run this command in Command Prompt (as Administrator):")
            print(f'   netstat -ano | findstr :{PORT}')
            print("   taskkill /PID <PID> /F")
            time.sleep(10)
            # Try to restart
            start_server()
        else:
            print(f"[ERROR] Server failed to start: {e}")
    except Exception as e:
        print(f"[ERROR] Server failed to start: {e}")

if __name__ == "__main__":
    start_server()