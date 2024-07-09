from flask import Flask, render_template, request, redirect, url_for ,session,jsonify
from pyModbusTCP.client import ModbusClient
import os
import requests
import threading
import time
import sqlite3

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'my_default_secret_key')


# Global variables section

#Ip addresses and ports
LK3_address = '127.0.0.1:8001' 
ET_7017_address = '10.10.251.50'
Modbus_lisent_address = '127.0.0.1'
Modbus_port = 5020

controller_data = {}
controller_data_ET_7017_10 = {}

HISTERESYS = 0.5
stare_bec = False
authenticated_already = False
server_LK3_controller_connection = True
username_for_login = ""
password_for_login = ""

def data_fetch():
    global controller_data
    global server_LK3_controller_connection
    while True:
        try:
            response = requests.get(f'http://{LK3_address}')
            response.raise_for_status() 
            data = response.json()
            controller_data = {
                'mac': data.get('mac', 'N/A'),
                'sw': data.get('sw', 'N/A'),
                'vin': data.get('vin', 'N/A'),
                'tem': data.get('tem', 'N/A'),
                'ds1' : data.get('ds1' , 'N/A')
            }
        except:
            # TODO handle the error
            if server_LK3_controller_connection == True:
                server_LK3_controller_connection = False
                print("Can't connect to LK3 controller server!")
        time.sleep(0.5)

data_thread = threading.Thread(target= data_fetch)
data_thread.daemon = True
data_thread.start()

def data_fetch_ET_7017_10():
    global controller_data_ET_7017_10
    global stare_bec
    global button_text
    while True:
        try:
            analog_input_register_address = 0
            client = ModbusClient(host=Modbus_lisent_address, port=Modbus_port)
            if client.open():
                values = client.read_input_registers(analog_input_register_address, 1)
                value = values[analog_input_register_address]
                value = (value - 65536 if value > 32767 else value) / 1000
                controller_data_ET_7017_10 = {'AI0' : value}
            if controller_data_ET_7017_10['AI0'] < 3 - HISTERESYS:
                #requests.get(f'http://{ET_7017_address}/outs.cgi?out0=0')
                print("Turned Off")
                stare_bec = False
            elif controller_data_ET_7017_10['AI0'] > 3 + HISTERESYS:
                #requests.get(f'http://{ET_7017_address}/outs.cgi?out0=1')
                print("Turned On")
                stare_bec = True
            button_text = 'Turn off' if stare_bec else 'Turn On'
        except:
            pass
        time.sleep(0.5)


data_thread_second = threading.Thread(target=data_fetch_ET_7017_10)
data_thread_second.daemon = True
data_thread_second.start()

@app.route('/', methods = ['GET'])
def index():
    if session.get('authenticated') == False: 
        return render_template('index.html')
    return redirect(url_for('home'))

@app.route('/signup' , methods = ['GET' , 'POST'])
def signup():
    global authenticated_already

    error = ""
    conn = sqlite3.connect('db.sqlite3')
    cursor = conn.cursor()

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        phone_nr = request.form['phone_nr']
        password = request.form['password']
        cursor.execute("SELECT * FROM credentials WHERE username = ? OR email = ?", (username, email))
        row = cursor.fetchone()

        if row:
            error = "Utilizatorul sau email-ul există deja!"
            username_for_login = username
            password_for_login = password
            authenticated_already = True
            return redirect(url_for('login'))
        else:
            try:
                cursor.execute(
                    "INSERT INTO credentials (username, email, password, phone_number) VALUES (?, ?, ?, ?)",
                    (username, email, password, phone_nr)
                )
                conn.commit()
                session['username'] = username
                session['authenticated'] = True
                conn.close()
                return redirect(url_for('home'))
            except sqlite3.Error as e:
                error = f"Eroare la inserarea în baza de date: {e}"

    conn.close()
    return render_template('sign_up.html', error=error)

@app.route('/login' , methods = ['GET' , 'POST'])
def login():
    global authenticated_already
    global username_for_login
    global password_for_login

    error = ""
    conn = sqlite3.connect('db.sqlite3')
    cursor = conn.cursor()
    if authenticated_already:
        username = username_for_login
        password = password_for_login
        session['username'] = username
        session['authenticated'] = True
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor.execute("SELECT * FROM credentials WHERE username = ? AND password = ?", (username, password))
        row = cursor.fetchone()
        if row:
            conn.close()
            session['username'] = username
            session['authenticated'] = True
            return redirect(url_for('home'))
        else:
            error = "Nu exita utilizatorul!"
    conn.close()
    return render_template('login.html', error=error)

@app.route('/runtime')
def runtime():
    return jsonify(controller_data)

@app.route('/runtime_E7')
def runtime_E7():
    return jsonify(controller_data_ET_7017_10)

@app.route('/home')
def home():
    global stare_bec
    global controller_data_ET_7017_10
    if session.get('authenticated') == False:
        return redirect(url_for('login'))
    try:
        response = requests.get(f'http://{LK3_address}')
        data = response.json()
        stare_bec = int(data['out0'])
    except:
        print("Can't acces LK3 server!")
    button_text = 'Turn on/off'
    print(stare_bec)
    return render_template('main.html' , button_text=button_text)

@app.route('/toggle' , methods = ['POST'])
def toggle():
    global stare_bec
    if stare_bec:
        #requests.get(f'http://{ET_7017_address}/outs.cgi?out0=0')
        print("Turned Off")
    else:
        #requests.get(f'http://{ET_7017_address}/outs.cgi?out0=1')
        print("Turned On")
    stare_bec = not stare_bec
    return redirect('/home')

@app.route('/logout', methods=['POST'])
def logout():
    session['authenticated'] = False
    return redirect(url_for('index'))

    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True) 
