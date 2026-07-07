from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_mysqldb import MySQL
from flask.json.provider import DefaultJSONProvider
from dotenv import load_dotenv
import os
import threading
import time
import unicodedata
from datetime import date, datetime

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None

try:
    from gpiozero import OutputDevice
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False
    OutputDevice = None

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'defaultsecretkey')

# receipt printer / scanner config
PRINTER_PORT = os.getenv('PRINTER_PORT', '/dev/ttyACM0')
PRINTER_BAUD = int(os.getenv('PRINTER_BAUD', '9600'))
PHARMACY_NAME = os.getenv('PHARMACY_NAME', 'Medicijnkluis')

# stepper motor config (carousel compartments)
STEPPER_STEP_DELAY = float(os.getenv('STEPPER_STEP_DELAY', '0.001'))  # seconds per step

serial_connection = None
serial_lock = threading.Lock()
latest_qr_code = None
serial_thread = None
serial_stop_event = threading.Event()

door_states = {}  # name -> bool (open/closed)

# stepper motor control (carousel)
stepper_pins = None
carousel_ready = True
stepper_thread = None
stepper_stop_event = threading.Event()
stepper_rotating = threading.Event()
stepper_rotation_start_time = None
stepper_target_duration = None
stepper_rotation_done = threading.Event()

STEPS_PER_COMPARTMENT = 9.1
TOTAL_COMPARTMENTS = 4          # adjust if you have more/fewer
CAROUSEL_STATE_FILE = '/home/buddyboys/project-b/carousel_position.txt'

def _load_carousel_position():
    """Load last known compartment from disk. Returns 1 if unknown."""
    try:
        with open(CAROUSEL_STATE_FILE, 'r') as f:
            val = int(f.read().strip())
            if 1 <= val <= TOTAL_COMPARTMENTS:
                return val
    except Exception:
        pass
    return 1

def _save_carousel_position(compartment):
    """Persist current compartment to disk."""
    try:
        with open(CAROUSEL_STATE_FILE, 'w') as f:
            f.write(str(compartment))
    except Exception as e:
        app.logger.warning('[carousel] failed to save position: %s', e)

# load position at startup — defaults to 1 on first run
current_compartment = _load_carousel_position()
app.logger.info('[carousel] starting at compartment %s', current_compartment)


def _shortest_path(current, target, total):
    """
    Return (steps, direction) for the shortest path between compartments.
    direction=1 is forward, direction=-1 is backward.
    steps is the number of compartment-steps to travel.
    """
    forward_steps = (target - current) % total
    backward_steps = (current - target) % total

    if forward_steps <= backward_steps:
        return forward_steps, 1
    else:
        return backward_steps, -1


def create_stepper():
    """Initialize the stepper motor pins."""
    global stepper_pins
    if not GPIOZERO_AVAILABLE or OutputDevice is None:
        app.logger.warning('[stepper] gpiozero not available on this system')
        return False
    try:
        stepper_pins = [
            OutputDevice(17),  # IN1
            OutputDevice(12),  # IN2
            OutputDevice(27),  # IN3
            OutputDevice(22),  # IN4
        ]
        # turn all pins off
        for pin in stepper_pins:
            pin.off()
        app.logger.info('[stepper] initialized on GPIOs 17, 12, 27, 22')
        return True
    except Exception as e:
        app.logger.warning('[stepper] init failed: %s', e)
        return False


def rotate_carousel(target_compartment, speed=STEPPER_STEP_DELAY, direction=None, wait=True):
    """Spin the carousel to the target compartment via the shortest path."""
    global carousel_ready, stepper_rotation_start_time, stepper_target_duration, current_compartment

    if stepper_pins is None:
        app.logger.info('[carousel] rotation requested (stepper unavailable)')
        return False

    # stop any ongoing rotation first
    if stepper_rotating.is_set():
        stop_carousel()
        stepper_rotation_done.wait(timeout=3)
        stepper_rotation_done.clear()

    steps, auto_direction = _shortest_path(current_compartment, target_compartment, TOTAL_COMPARTMENTS)
    if direction is None:
        direction = auto_direction

    if steps == 0:
        app.logger.info('[carousel] already at compartment %s, no rotation needed', target_compartment)
        return True

    duration = steps * STEPS_PER_COMPARTMENT
    carousel_ready = False
    stepper_stop_event.clear()
    stepper_rotating.set()
    stepper_rotation_done.clear()
    stepper_rotation_start_time = time.time()
    stepper_target_duration = duration

    app.logger.info(
        '[carousel] %s → %s: %s compartment(s) %s (%.1fs)',
        current_compartment, target_compartment,
        steps, 'forward' if direction == 1 else 'backward', duration
    )

    def _run():
        stepperMotor(duration, direction)
        # update and persist position only after successful completion
        if not stepper_stop_event.is_set():
            global current_compartment
            current_compartment = target_compartment
            _save_carousel_position(current_compartment)
            app.logger.info('[carousel] arrived at compartment %s', current_compartment)

    stepper_thread = threading.Thread(target=_run, daemon=True)
    stepper_thread.start()

    if wait:
        stepper_rotation_done.wait()

    return True


def stop_carousel():
    """Stop the currently running carousel rotation."""
    if not stepper_rotating.is_set():
        return False
    app.logger.info('[carousel] stopping rotation early')
    stepper_stop_event.set()
    return True


def stepperMotor(duration_seconds, direction=1):
    """Run the stepper motor for the given duration and direction."""
    global carousel_ready
    if stepper_pins is None:
        stepper_rotating.clear()
        stepper_rotation_done.set()
        return

    sequence = [
        [1, 0, 0, 0],
        [1, 1, 0, 0],
        [0, 1, 0, 0],
        [0, 1, 1, 0],
        [0, 0, 1, 0],
        [0, 0, 1, 1],
        [0, 0, 0, 1],
        [1, 0, 0, 1]
    ]

    seq = sequence if direction == 1 else sequence[::-1]
    end_time = time.time() + duration_seconds

    try:
        while time.time() < end_time:
            # check stop signal
            if stepper_stop_event.is_set():
                app.logger.info('[stepper] stop signal received')
                break
            for step in seq:
                if time.time() >= end_time:
                    break
                # check stop signal between steps too
                if stepper_stop_event.is_set():
                    app.logger.info('[stepper] stop signal received')
                    break
                for pin, state in zip(stepper_pins, step):
                    pin.on() if state else pin.off()
                time.sleep(STEPPER_STEP_DELAY)
    finally:
        for pin in stepper_pins:
            pin.off()
        stepper_rotating.clear()
        carousel_ready = True
        stepper_rotation_done.set()


# initialize the stepper motor at startup
create_stepper()


def open_door(name='compartment', angle=None):
    """Send DOOR:OPEN command to Arduino over serial."""
    try:
        conn = ensure_serial_connection()
        if conn is None:
            app.logger.warning('[door:%s] serial not available', name)
            return False
        with serial_lock:
            conn.write(b'DOOR:OPEN\n')
            conn.flush()
        door_states[name] = True
        app.logger.info('[door:%s] opened via Arduino', name)
        return True
    except Exception as e:
        app.logger.error('[door:%s] open failed: %s', name, e)
        return False


def close_door(name='compartment', angle=None):
    """Send DOOR:CLOSE command to Arduino over serial."""
    try:
        conn = ensure_serial_connection()
        if conn is None:
            app.logger.warning('[door:%s] serial not available', name)
            return False
        with serial_lock:
            conn.write(b'DOOR:CLOSE\n')
            conn.flush()
        door_states[name] = False
        app.logger.info('[door:%s] closed via Arduino', name)
        return True
    except Exception as e:
        app.logger.error('[door:%s] close failed: %s', name, e)
        return False


def get_available_serial_ports():
    if not list_ports:
        return []
    try:
        return [port.device for port in list_ports.comports()]
    except Exception:
        return []


def get_printer_port_candidates():
    candidates = []
    configured_port = (os.getenv('PRINTER_PORT', '') or '').strip()
    if configured_port:
        candidates.append(configured_port)

    for candidate in [
        '/dev/ttyUSB0',
        '/dev/ttyACM0',
        '/dev/ttyAMA0',
        '/dev/serial0',
        'COM1',
        'COM2',
        'COM3',
        'COM4',
        'COM5',
        'COM6',
    ]:
        if candidate not in candidates:
            candidates.append(candidate)

    for port in get_available_serial_ports():
        if port not in candidates:
            candidates.append(port)

    return candidates


def sanitize_print_text(value):
    if value is None:
        return ''
    if not isinstance(value, str):
        value = str(value)
    normalized = unicodedata.normalize('NFKD', value)
    return normalized.encode('ascii', 'replace').decode('ascii')


def ensure_serial_connection():
    global serial_connection
    if serial_connection and serial_connection.is_open:
        return serial_connection
    if serial is None:
        return None
    try:
        serial_connection = serial.Serial(PRINTER_PORT, PRINTER_BAUD, timeout=1)
        app.logger.info('Opened serial port %s for printer/scanner', PRINTER_PORT)
        return serial_connection
    except Exception as e:
        app.logger.error('Unable to open serial port %s: %s', PRINTER_PORT, e)
        serial_connection = None
        return None


def serial_reader_loop():
    global latest_qr_code, serial_connection
    while not serial_stop_event.is_set():
        conn = ensure_serial_connection()
        if conn is None:
            time.sleep(1)
            continue

        try:
            line = conn.readline()
            if not line:
                continue
            try:
                text = line.decode('utf-8', errors='ignore').strip()
            except Exception:
                continue

            if text.startswith('SCAN:'):
                code = text.split('SCAN:', 1)[1].strip()
                if code:
                    latest_qr_code = code
                    app.logger.info('QR code scanned: %s', code)
        except Exception as e:
            app.logger.error('Serial reader error: %s', e)
            time.sleep(1)


def start_serial_thread():
    global serial_thread
    if serial_thread is not None:
        return
    if serial is None:
        app.logger.warning('pyserial is not installed; QR scanning disabled')
        return

    # open connection now so the scanner thread can read immediately
    ensure_serial_connection()
    serial_thread = threading.Thread(target=serial_reader_loop, daemon=True)
    serial_thread.start()


@app.route('/api/qr/scan', methods=['GET'])
def qr_scan():
    global latest_qr_code
    code = latest_qr_code
    latest_qr_code = None
    return jsonify({'qr_code': code}), 200


class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


app.json_provider_class = CustomJSONProvider
app.json = CustomJSONProvider(app)

# mysql configuration from environment variables
app.config['MYSQL_HOST'] = os.getenv('DB_HOST', 'localhost')
app.config['MYSQL_USER'] = os.getenv('DB_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('DB_PASSWORD', '')
app.config['MYSQL_DB'] = os.getenv('DB_NAME', 'medicine_vault')
app.config['MYSQL_PORT'] = int(os.getenv('DB_PORT', 3306))

mysql = MySQL(app)

# only table the admin dashboard may query (read-only)
ALLOWED_ADMIN_TABLE = 'orders'

@app.route('/')
def index():
    return render_template('index.html')


# api: health check / connection test
@app.route('/api/db-status')
def db_status():
    try:
        cur = mysql.connection.cursor()
        cur.execute('SELECT 1')
        cur.close()
        return jsonify({'status': 'connected'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# admin helper
def is_admin():
    return session.get('admin_authenticated', False)


# admin pages
@app.route('/admin')
def admin():
    if not is_admin():
        return redirect(url_for('admin_login'))
    return render_template('admin.html')


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if is_admin():
        return redirect(url_for('admin'))

    if request.method == 'POST':
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'error': 'Invalid request'}), 400

        pincode = data.get('pincode', '')
        env_pin = os.getenv('ADMIN_PINCODE', '')

        if pincode == env_pin:
            session['admin_authenticated'] = True
            return jsonify({'status': 'ok'})
        else:
            return jsonify({'error': 'Invalid credentials'}), 401

    return render_template('admin_login.html')


@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('admin_authenticated', None)
    return jsonify({'status': 'ok'})


DISPLAY_COLUMNS = ['order_id', 'product_id', 'product_name', 'amount', 'compartment_number', 'status', 'pincode', 'birthdate', 'created_at', 'updated_at']
EDITABLE_COLUMNS = ['compartment_number', 'status']


def cursor_to_dicts(cur, columns_filter=None):
    """Convert cursor result to list of dicts using column names from cursor.description."""
    rows = cur.fetchall()
    if not rows:
        return []
    col_names = [col[0] for col in cur.description]
    if columns_filter:
        indices = [col_names.index(c) for c in columns_filter if c in col_names]
        filtered_names = [col_names[i] for i in indices]
        return [dict(zip(filtered_names, [row[i] for i in indices])) for row in rows]
    return [dict(zip(col_names, row)) for row in rows]


def row_to_dict(row, col_names, columns_filter=None):
    """Convert a single row tuple to dict using column names."""
    if row is None:
        return None
    if columns_filter:
        indices = [col_names.index(c) for c in columns_filter if c in col_names]
        filtered_names = [col_names[i] for i in indices]
        return dict(zip(filtered_names, [row[i] for i in indices]))
    return dict(zip(col_names, row))


# admin dropdown options (compartments & statuses)
@app.route('/api/admin/options', methods=['GET'])
def admin_options():
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 401

    # hardcoded statuses that should always be available
    all_statuses = ['pending', 'ready', 'completed', 'cancelled']

    return jsonify({
        'compartments': [1, 2, 3, 4],
        'statuses': all_statuses
    }), 200


@app.route('/api/admin/compartments', methods=['GET'])
def admin_compartments():
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 401

    cur = mysql.connection.cursor()
    try:
        cur.execute(
            f'SELECT id, order_id, product_id, product_name, amount, compartment_number, status, pincode, birthdate, created_at, updated_at FROM `{ALLOWED_ADMIN_TABLE}` ORDER BY (compartment_number IS NULL), compartment_number, id'
        )
        rows = cursor_to_dicts(cur)
        compartment_numbers = [1, 2, 3, 4]
        grouped = []
        for compartment_number in compartment_numbers:
            grouped.append({
                'number': compartment_number,
                'orders': [row for row in rows if row.get('compartment_number') == compartment_number]
            })

        unassigned_orders = [row for row in rows if row.get('compartment_number') is None and str(row.get('status', '')).lower() == 'pending']
        return jsonify({
            'compartments': grouped,
            'unassigned_orders': unassigned_orders
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()


# admin orders read
@app.route('/api/admin/orders', methods=['GET'])
def admin_orders():
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 401

    cur = mysql.connection.cursor()
    try:
        columns_select = ', '.join(['id'] + DISPLAY_COLUMNS)
        cur.execute(f'SELECT {columns_select} FROM `{ALLOWED_ADMIN_TABLE}` LIMIT 500')
        results = cursor_to_dicts(cur)
        return jsonify(results), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()


# admin edit order (compartment_number and status only)
@app.route('/api/admin/orders/<int:order_id>', methods=['PUT'])
def admin_edit_order(order_id):
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON body'}), 400

    cur = mysql.connection.cursor()
    try:
        # check if the order exists
        cur.execute(f'SELECT id FROM `{ALLOWED_ADMIN_TABLE}` WHERE id = %s', (order_id,))
        if not cur.fetchone():
            return jsonify({'error': 'Order not found'}), 404

        # only allow editing specific fields
        updates = {}
        for k in EDITABLE_COLUMNS:
            if k in data:
                updates[k] = data[k]

        # auto-sync status with compartment assignment (but don't pull completed orders back)
        if 'compartment_number' in updates:
            cur.execute(
                f'SELECT status FROM `{ALLOWED_ADMIN_TABLE}` WHERE id = %s',
                (order_id,)
            )
            current_row = cur.fetchone()
            current_status = current_row[0] if current_row else None

            if updates['compartment_number'] is not None:
                updates['status'] = 'ready'
            elif current_status != 'completed':
                # only revert to pending if the order hasn't been completed yet
                updates['status'] = 'pending'

        if not updates:
            return jsonify({'error': 'No valid fields to update'}), 400

        set_clause = ', '.join(f'`{k}` = %s' for k in updates)
        values = list(updates.values()) + [order_id]
        cur.execute(f'UPDATE `{ALLOWED_ADMIN_TABLE}` SET {set_clause} WHERE id = %s', values)
        mysql.connection.commit()
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()


# admin delete order
@app.route('/api/admin/orders/<int:order_id>', methods=['DELETE'])
def admin_delete_order(order_id):
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 401

    cur = mysql.connection.cursor()
    try:
        cur.execute(f'DELETE FROM `{ALLOWED_ADMIN_TABLE}` WHERE id = %s', (order_id,))
        if cur.rowcount == 0:
            return jsonify({'error': 'Order not found'}), 404
        mysql.connection.commit()
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()


# user login with pincode or birthdate
@app.route('/api/user/login', methods=['POST'])
def user_login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    pincode = data.get('pincode')
    birthdate = data.get('birthdate')   # expected: 'YYYY-MM-DD'
    qr_code = data.get('qr_code')

    if not pincode and not birthdate and not qr_code:
        return jsonify({'error': 'No credentials provided'}), 400

    if qr_code and not pincode:
        pincode = qr_code

    cur = mysql.connection.cursor()
    try:
        columns_select = ', '.join(['id', 'product_name', 'amount', 'compartment_number', 'status', 'pincode', 'birthdate', 'created_at', 'updated_at'])
        if pincode:
            # find orders that match this pincode and are either 'pending' or 'ready'
            cur.execute(
                f'SELECT {columns_select} FROM `{ALLOWED_ADMIN_TABLE}` WHERE pincode = %s AND status IN ("pending", "ready")',
                (pincode,)
            )
        elif birthdate:
            cur.execute(
                f'SELECT {columns_select} FROM `{ALLOWED_ADMIN_TABLE}` WHERE birthdate = %s AND status IN ("pending", "ready")',
                (birthdate,)
            )
        else:
            return jsonify({'error': 'No valid login method'}), 400

        results = cursor_to_dicts(cur)
        if not results:
            return jsonify({'error': 'Geen openstaande orders gevonden. / No open orders found.'}), 404

        return jsonify(results), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()


# user picks up an order (updates status + triggers dispensing)
@app.route('/api/user/pickup/<int:order_id>', methods=['POST'])
def user_pickup(order_id):
    cur = mysql.connection.cursor()
    try:
        cur.execute(
            f'SELECT id, compartment_number, status FROM `{ALLOWED_ADMIN_TABLE}` WHERE id = %s',
            (order_id,)
        )
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Order not found'}), 404

        if row[2] not in ('pending', 'ready'):
            return jsonify({'error': 'Order is not available for pickup'}), 400

        compartment = row[1]
        if compartment is None:
            return jsonify({'error': 'Vak nog niet toegewezen / Compartment not assigned yet'}), 400

        # Spin the carousel to the correct compartment first
        rotate_carousel(compartment)

        # Then open the compartment door
        open_door()

        # DO NOT change status yet - wait until user finishes
        # Status stays 'ready' during dispensing
        return jsonify({'status': 'ok', 'compartment': compartment}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()


# print receipt on thermal printer
@app.route('/api/print/receipt', methods=['POST'])
def print_receipt():
    data = request.get_json(silent=True)
    if not data or 'order_id' not in data:
        return jsonify({'error': 'Order ID required'}), 400

    order_id = data['order_id']
    cur = mysql.connection.cursor()
    try:
        # fetch order details and customer name from the users table
        cur.execute(
            'SELECT o.product_name, o.amount, o.compartment_number, o.order_id, u.name FROM orders o LEFT JOIN users u ON o.user_id = u.id WHERE o.id = %s',
            (order_id,)
        )
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Order not found'}), 404

        product_name = sanitize_print_text(row[0] or 'Medicijn')
        amount = row[1] or 0
        compartment = row[2]
        external_order_id = sanitize_print_text(str(row[3]) if row[3] else '')
        customer_name = sanitize_print_text(row[4]) if row[4] else 'Klant'
        pharmacy_name = sanitize_print_text(PHARMACY_NAME)

        today = datetime.now().strftime('%d-%m-%Y')

        # build receipt text
        lines = [
            pharmacy_name,
            '',
            f'Datum: {today}',
            f'Bestelling: {external_order_id}',
            f'Naam: {customer_name}',
            '',
            'Medicijnen:',
            f'  {product_name} x{amount}',
            '',
        ]
        if compartment is not None:
            lines.append(f'Vak: {compartment}')
        lines.extend(['', '---- Eind bonnetje ----', '', '', '', ''])

        receipt_text = '\n'.join(lines)

        # send to printer via Arduino
        if serial is None:
            return jsonify({'error': 'Printer support is unavailable. Install pyserial first.'}), 500

        conn = ensure_serial_connection()
        if conn is None:
            return jsonify({
                'error': 'Printer error',
                'details': f'Unable to open serial port {PRINTER_PORT}.',
                'configured_port': PRINTER_PORT,
                'available_ports': get_available_serial_ports(),
            }), 500

        try:
            with serial_lock:
                time.sleep(1.5)  # let the Arduino settle before sending
                # send ESC/POS init + full receipt to Arduino (which forwards to printer)
                # each line terminated with \n — Arduino forwards non-DOOR lines to printer
                payload = b'\x1b\x40\n' + (receipt_text + '\n').encode('ascii', 'replace') + b'\x1b\x64\x03\n'
                conn.write(payload)
                conn.flush()
        except (serial.SerialException, OSError) as exc:
            error_msg = str(exc)
            app.logger.error(
                'Printer write failed on %s: %s',
                PRINTER_PORT,
                error_msg,
            )
            return jsonify({'error': 'Printer error', 'details': error_msg}), 500
        
        # also set order to completed on successful print
        try:
            cur.execute(
                f'UPDATE `{ALLOWED_ADMIN_TABLE}` SET status = %s WHERE id = %s',
                ('completed', order_id)
            )
            mysql.connection.commit()
        except:
            pass
        
        return jsonify({'status': 'ok'}), 200
    finally:
        cur.close()


# user completes their pickup (sets order to completed)
@app.route('/api/user/complete/<int:order_id>', methods=['POST'])
def user_complete(order_id):
    cur = mysql.connection.cursor()
    try:
        cur.execute(
            f'UPDATE `{ALLOWED_ADMIN_TABLE}` SET status = %s WHERE id = %s',
            ('completed', order_id)
        )
        mysql.connection.commit()

        # Close the compartment door
        close_door()

        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()


# user failed to complete pickup (inactivity timeout — sets order to failed_to_pickup)
@app.route('/api/user/failed_pickup/<int:order_id>', methods=['POST'])
def user_failed_pickup(order_id):
    cur = mysql.connection.cursor()
    try:
        cur.execute(
            f'UPDATE `{ALLOWED_ADMIN_TABLE}` SET status = %s WHERE id = %s',
            ('failed_to_pickup', order_id)
        )
        mysql.connection.commit()

        # Close the compartment door
        close_door()

        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()


@app.route('/api/door/close', methods=['POST'])
def api_close_door():
    """Close the compartment door (leave carousel to finish on its own)."""
    try:
        close_door()
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/door/open', methods=['POST'])
def api_admin_door_open():
    """Open the compartment door (admin)."""
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        open_door()
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/door/close', methods=['POST'])
def api_admin_door_close():
    """Close the compartment door (admin)."""
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        close_door()
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/carousel/rotate/<int:compartment>', methods=['POST'])
def api_admin_rotate_carousel(compartment):
    """Rotate the carousel to a specific compartment (admin)."""
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        # wait=False so the request returns immediately while rotation runs in background
        rotate_carousel(compartment, wait=False)
        return jsonify({'status': 'ok', 'compartment': compartment}), 202
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    start_serial_thread()
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False, threaded=True)