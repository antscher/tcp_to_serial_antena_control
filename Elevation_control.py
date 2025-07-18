import socket
import time
import threading
import serial

# Paramètres
TCP_HOST = "localhost"
TCP_PORT = 4533

SERIAL_PORT = "COM3"   # Modifie ici pour ton port réel
SERIAL_BAUD = 9600

# Position actuelle d'azimut
current_az = 0.0

lock = threading.Lock()

# Thread pour lire les retours du moteur
def serial_reader(ser):
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


def main():
    # Initialisation série
    ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
    time.sleep(2)  # Attente d'initialisation

    # Lance le thread série
    threading.Thread(target=serial_reader, args=(ser,), daemon=True).start()

    # Serveur TCP
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((TCP_HOST, TCP_PORT))
    server_socket.listen(1)

    print(f"Attente de connexion Gpredict sur {TCP_HOST}:{TCP_PORT}...")

    while True:
        conn, addr = server_socket.accept()
        print(f"Connexion de {addr}")

        while True:
            data = conn.recv(1024)
            if not data:
                break

            command = data.decode().strip()
            print(f"Commande reçue : {command}")

            if command == "p":
                with lock:
                    response = f"{current_az:.1f}\n{0.0:.1f}\n"   # Elévation fixée à 0.0
                conn.sendall(response.encode())
                print(f"Réponse envoyée : {response.strip()}")

            elif command.startswith("P "):
                parts = command.split()
                if len(parts) == 3:
                    az = float(parts[1].replace(",", "."))

                    # Envoie la commande d'azimut au moteur
                    cmd = f"A{az:.1f}\r"
                    ser.write(cmd.encode())
                    print(f"[SERIAL] Commande envoyée : {cmd.strip()}")
                    response = f"{current_az:.1f}\n{0.0:.1f}\n"   # Elévation fixée à 0.0
                    conn.sendall(response.encode())
                    print(f"Réponse envoyée : {response.strip()}")

        conn.close()

if __name__ == "__main__":
    main()
