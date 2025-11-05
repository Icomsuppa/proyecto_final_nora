# flask_microservice/clients/console_client.py
import requests
from datetime import datetime

URL = "http://{host}:5000/time/".format(host="127.0.0.1")  # reemplaza por la IP del servidor si corres desde otra máquina

def main():
    try:
        r = requests.get(URL, timeout=5)
        r.raise_for_status()
        data = r.json()
        server_time = data['time']  # HH:MM:SS
        server_dt = datetime.strptime(data['date'] + ' ' + server_time, '%Y-%m-%d %H:%M:%S')
        local_dt = datetime.now()
        diff = (local_dt - server_dt).total_seconds()
        print("Servidor:", server_dt)
        print("Local:   ", local_dt)
        if diff > 0:
            print(f"La hora local está {diff:.2f} segundos ADELANTADA.")
        elif diff < 0:
            print(f"La hora local está {-diff:.2f} segundos ATRASADA.")
        else:
            print("Las horas coinciden exactamente.")
    except requests.exceptions.Timeout:
        print("Error: Tiempo de espera excedido (5000 ms).")
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    main()
