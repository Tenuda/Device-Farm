from flask import Flask, jsonify
from flask_socketio import SocketIO, emit
import pyudev
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize pyudev context and monitor
context = pyudev.Context()
monitor = pyudev.Monitor.from_netlink(context)
monitor.filter_by(subsystem='usb')

# List to hold connected devices
connected_devices = []
device_lock = threading.Lock()

# Set to avoid processing the same event multiple times
processed_devices = set()

def update_device_list(action, device):
    global connected_devices
    with device_lock:
        serial = device.get('ID_SERIAL_SHORT', None)
        model = device.get('ID_MODEL', None)
        vendor_id = device.get('ID_VENDOR_ID', None)
        model_id = device.get('ID_MODEL_ID', None)
        sysFS_ID = device.get('DEVPATH', None)
        bus_ID = device.get('BUSNUM', None)
        seq_NUM = device.get('SEQNUM', None)
        dev_ID = device.get('DEVNUM', None)

        if action == 'remove':
            connected_devices[:] = [
                dev for dev in connected_devices
                if dev['sysFS_ID'] != sysFS_ID and dev['seq_NUM'] != seq_NUM and dev['dev_ID'] != dev_ID
            ]
            processed_devices.discard(sysFS_ID)
            socketio.emit('update', {'devices': connected_devices})  # Send the updated list via WebSocket
            return

        if action == 'add':
            if vendor_id and model_id and serial not in processed_devices:
                connected_devices.append({
                    'device_name': model,
                    'vendor_id': vendor_id,
                    'product_id': model_id,
                    'serial': serial,
                    'sysFS_ID': sysFS_ID,
                    'bus_ID': bus_ID,
                    'dev_ID': dev_ID,
                    'seq_NUM': seq_NUM,
                    'status': 'online'
                })
                processed_devices.add(sysFS_ID)
                socketio.emit('update', {'devices': connected_devices})  # Send the updated list via WebSocket

def monitor_usb_events():
    for action, device in monitor:
        time.sleep(0.5)
        update_device_list(action, device)

@app.route('/', methods=['GET'])
def get_connected_devices():
    with device_lock:
        filter_devices = [device for device in connected_devices if device['serial'] is not None]
        return jsonify({
            'devices': filter_devices,
            'count': len(filter_devices)
        })

if __name__ == '__main__':
    # Run the USB event monitor in a separate thread
    monitor_thread = threading.Thread(target=monitor_usb_events, daemon=True)
    monitor_thread.start()

    # Start Flask server with WebSocket support
    socketio.run(app, host='0.0.0.0', port=5001)
