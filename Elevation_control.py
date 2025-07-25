import socket
import time
import threading
import serial

# TCP parameters for Gpredict
TCP_HOST = "localhost"
TCP_PORT = 4533

# Serial parameters
SERIAL_PORT = "COM7"   # Replace with your elevation COM port
SERIAL_BAUD = 9600

# Current elevation position (updated by serial feedback)
current_el = 0.0

# Lock to protect shared variable access between threads
lock = threading.Lock()

def serial_reader(ser):
    """
    Thread function to read serial data from the motor controller.
    Parses the feedback and updates the current elevation.
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

def tcp_server(ser):
    """
    TCP server to communicate with Gpredict using rotctl protocol.
    Handles 'p' for position request and 'P az el' for movement commands.
    """
    global current_el

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
                # Gpredict requests current position (azimuth is fixed to 0.0)
                with lock:
                    response = f"{0.0:.1f}\n{current_el:.1f}\n"
                conn.sendall(response.encode())
                print(f"Position sent: {response.strip()}")

            elif command.startswith("P "):
                # Gpredict sends a move command (P <az> <el>)
                parts = command.split()
                if len(parts) == 3:
                    el = float(parts[2].replace(",", "."))

                    # Format motor controller command: E<el> with carriage return
                    cmd = f"E{el:.1f}\r"
                    ser.write(cmd.encode())

                    print(f"[SERIAL] Command sent: {cmd.strip()}")

                    # Send back current position after command
                    with lock:
                        response = f"{0.0:.1f}\n{current_el:.1f}\n"
                    conn.sendall(response.encode())
                    print(f"Position sent: {response.strip()}")

        conn.close()  # Close connection when client disconnects

def main():
    """
    Main function to initialize the serial port, start the serial reader thread,
    and run the TCP server for Gpredict communication.
    """
    # Initialize serial connection
    ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
    time.sleep(2)  # Allow time for serial port to initialize

    # Launch serial reader thread
    threading.Thread(target=serial_reader, args=(ser,), daemon=True).start()

    # Start TCP server loop
    tcp_server(ser)

if __name__ == "__main__":
    main()
