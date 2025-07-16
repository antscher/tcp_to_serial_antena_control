import socket
import time
import threading
import serial

# TCP parameters for Gpredict
TCP_HOST = "localhost"
TCP_PORT = 4533

# Serial ports for azimuth and elevation (Set your correct COM ports here)
COM_AZ = "COM3"   # Replace with your azimuth COM port
COM_EL = "COM4"   # Replace with your elevation COM port
SERIAL_BAUD = 9600

# Current positions (updated by serial feedback)
current_az = 0.0
current_el = 0.0

# Lock to ensure thread-safe updates of shared variables
lock = threading.Lock()

def read_serial(ser, axis):
    """
    Thread function to read serial data from the motor controller.
    Parses the feedback and updates the current position for azimuth or elevation.
    """
    global current_az, current_el

    while True:
        line = ser.readline().decode(errors='ignore').strip()
        if not line:
            continue  # Skip empty lines

        # Expecting feedback in format: A=xxx.x S=x M or E=xxx.x S=x M
        if line.startswith(axis + "="):
            parts = line.split()
            pos = float(parts[0][2:])  # Extract numeric position

            # Update global position in a thread-safe way
            with lock:
                if axis == "A":
                    current_az = pos
                else:
                    current_el = pos

            print(f"[{axis}] Feedback: {line}")

        elif line.startswith("ERR="):
            print(f"[{axis}] ERROR: {line}")

def tcp_server(ser_az, ser_el):
    """
    TCP server to communicate with Gpredict using rotctl protocol.
    Handles 'p' for position request and 'P az el' for movement commands.
    """
    global current_az, current_el

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((TCP_HOST, TCP_PORT))
    server_socket.listen(1)

    print(f"Waiting for Gpredict connection on {TCP_HOST}:{TCP_PORT}...")

    while True:
        conn, addr = server_socket.accept()
        print(f"Connected to {addr}")

        while True:
            data = conn.recv(1024)
            if not data:
                break  # Client disconnected

            command = data.decode().strip()
            print(f"Command received: {command}")

            if command == "p":
                # Gpredict asks for current position
                with lock:
                    response = f"{current_az:.1f}\n{current_el:.1f}\n"
                conn.sendall(response.encode())
                print(f"Position sent: {response.strip()}")

            elif command.startswith("P "):
                # Gpredict sends a move command (P <az> <el>)
                parts = command.split()
                if len(parts) == 3:
                    az = float(parts[1].replace(",", "."))
                    el = float(parts[2].replace(",", "."))

                    # Format motor controller commands: A<az> and E<el> with carriage return
                    cmd_az = f"A{az:.1f}\r"
                    cmd_el = f"E{el:.1f}\r"

                    # Send commands to azimuth and elevation controllers
                    ser_az.write(cmd_az.encode())
                    ser_el.write(cmd_el.encode())

                    print(f"[AZ] Command sent: {cmd_az.strip()}")
                    print(f"[EL] Command sent: {cmd_el.strip()}")

        conn.close()  # Close TCP connection when client disconnects

def main():
    """
    Main function to initialize serial ports, start serial reading threads, 
    and run the TCP server for Gpredict communication.
    """
    # Initialize serial connections
    ser_az = serial.Serial(COM_AZ, SERIAL_BAUD, timeout=1)
    ser_el = serial.Serial(COM_EL, SERIAL_BAUD, timeout=1)
    time.sleep(2)  # Allow time for serial ports to initialize

    # Launch reading threads for azimuth and elevation
    threading.Thread(target=read_serial, args=(ser_az, "A"), daemon=True).start()
    threading.Thread(target=read_serial, args=(ser_el, "E"), daemon=True).start()

    # Start TCP server loop
    tcp_server(ser_az, ser_el)

if __name__ == "__main__":
    main()
