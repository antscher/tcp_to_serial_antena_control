import socket
import time
import threading
import serial

# TCP server parameters for Gpredict
TCP_HOST = "localhost"
TCP_PORT = 4533

# Serial parameters
SERIAL_AZ_PORT = "COM26"   # Replace with your azimuth COM port
SERIAL_EL_PORT = "COM7"   # Replace with your elevation COM port
SERIAL_BAUD = 9600

# Shared current positions
current_az = 0.0
current_el = 0.0

# Locks for thread-safe variable access
lock = threading.Lock()

def serial_reader_az(ser):
    """
    Thread function to read AZIMUTH feedback from the controller.
    """
    global current_az

    while True:
        line = ser.readline().decode(errors='ignore').strip()
        if not line:
            continue

        if line.startswith("A="):
            parts = line.split()
            az = float(parts[0][2:])
            with lock:
                current_az = az
            print(f"[SERIAL] {line}")

        elif line.startswith("ERR="):
            print(f"[SERIAL] ERREUR: {line}")

def serial_reader_el(ser):
    """
    Thread function to read ELEVATION feedback from the controller.
    """
    global current_el

    while True:
        line = ser.readline().decode(errors='ignore').strip()
        if not line:
            continue  # Skip empty lines

        # Expecting feedback in format: E=xxx.x S=x M or E=xxx.x S=x S
        if line.startswith("E="):
            parts = line.split()
            el = float(parts[0][2:])  # Extract elevation value

            # Thread-safe update of the shared variable
            with lock:
                current_el = el

            print(f"[SERIAL] Feedback: {line}")

        elif line.startswith("ERR="):
            print(f"[SERIAL] ERROR: {line}")


def tcp_server(ser_az, ser_el):
    """
    TCP server compatible with Gpredict.
    Handles position requests and movement commands for AZ and EL.
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
            print(f"[TCP] Command received: {command}")

            if command == "p":
                # Return current position
                with lock:
                    response = f"{current_az:.1f}\n{current_el:.1f}\n"
                conn.sendall(response.encode())
                print(f"[TCP] Position sent: {response.strip()}")

            elif command.startswith("P "):
                # Move to new position: P <az> <el>
                parts = command.split()
                if len(parts) == 3:
                    az = float(parts[1].replace(",", "."))
                    el = float(parts[2].replace(",", "."))

                    # Send commands to azimuth and elevation controllers
                    cmd_az = f"A{az:.1f}\r"
                    cmd_el = f"E{el:.1f}\r"

                    ser_az.write(cmd_az.encode())
                    time.sleep(0.5) 
                    ser_el.write(cmd_el.encode())

                    print(f"[AZIMUTH SERIAL] Command sent: {cmd_az.strip()}")
                    print(f"[ELEVATION SERIAL] Command sent: {cmd_el.strip()}")

                    # Return updated positions (instantaneous)
                    with lock:
                        response = f"{current_az:.1f}\n{current_el:.1f}\n"
                    conn.sendall(response.encode())
                    print(f"[TCP] Position sent: {response.strip()}")

                if command == "S" or command == "q" :
                    break  # Exit the loop to stop the server 

        conn.close()
        print("[TCP] Client disconnected")

def main():
    """
    Main function to initialize serial ports, start serial reading threads, 
    and run the TCP server for Gpredict communication.
    """
    # Initialize serial connections
    ser_az = serial.Serial(SERIAL_AZ_PORT, SERIAL_BAUD, timeout=1)
    ser_el = serial.Serial(SERIAL_EL_PORT, SERIAL_BAUD, timeout=1)
    time.sleep(2)  # Allow time for serial ports to initialize

    # Launch reading threads for azimuth and elevation
    threading.Thread(target=serial_reader_az, args=(ser_az,), daemon=True).start()
    threading.Thread(target=serial_reader_el, args=(ser_el,), daemon=True).start()

    # Start TCP server loop
    tcp_server(ser_az, ser_el)


if __name__ == "__main__":
    main()
