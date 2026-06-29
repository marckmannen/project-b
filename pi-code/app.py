from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_mysqldb import MySQL
from flask.json.provider import DefaultJSONProvider
from dotenv import load_dotenv
import os
import json
import serial
from datetime import date, datetime

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'defaultsecretkey')

# receipt printer config
PRINTER_PORT = os.getenv('PRINTER_PORT', '/dev/ttyACM0')
PRINTER_BAUD = int(os.getenv('PRINTER_BAUD', '9600'))
PHARMACY_NAME = os.getenv('PHARMACY_NAME', 'Medicijnkluis')


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

        username = data.get('username', '')
        password = data.get('password', '')

        env_user = os.getenv('ADMIN_USERNAME', '')
        env_pass = os.getenv('ADMIN_PASSWORD', '')

        if username == env_user and password == env_pass:
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

    if not pincode and not birthdate:
        return jsonify({'error': 'No credentials provided'}), 400

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

        # update status to ready (for pickup flow)
        cur.execute(
            f'UPDATE `{ALLOWED_ADMIN_TABLE}` SET status = %s WHERE id = %s',
            ('ready', order_id)
        )
        mysql.connection.commit()
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
        # fetch order + user info
        cur.execute(
            'SELECT o.product_name, o.amount, o.compartment_number, o.birthdate, '
            '       u.name, o.pharmacy_id '
            'FROM orders o '
            'LEFT JOIN users u ON o.user_id = u.id '
            'WHERE o.id = %s',
            (order_id,)
        )
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Order not found'}), 404

        product_name = row[0] or '—'
        amount = row[1] or 0
        compartment = row[2]
        birthdate = row[3] or '—'
        patient_name = row[4] or 'Klant'
        pharmacy_id = row[5] or PHARMACY_NAME

        # use pharmacy name from env if available, else fallback
        pharmacy = PHARMACY_NAME

        today = datetime.now().strftime('%d-%m-%Y')

        # build receipt text
        lines = [
            pharmacy,
            '',
            f'Datum: {today}',
            f'Naam: {patient_name}',
            '',
            'Medicijnen:',
            f'  {product_name} x{amount}',
            '',
        ]
        if compartment is not None:
            lines.append(f'Vak: {compartment}')
        lines.extend(['', '---- Ei\[nd bonnetje ----', '', '', '', ''])

        receipt_text = '\n'.join(lines)

        # send to printer
        try:
            ser = serial.Serial(PRINTER_PORT, PRINTER_BAUD, timeout=1)
            try:
                ser.write(b'\x1b\x40')  # ESC @ — init printer
                for char in receipt_text.encode('latin-1'):
                    ser.write(bytes([char]))
                ser.write(b'\x1d\x56\x01')  # GS V 1 — cut paper
            finally:
                ser.close()
        except serial.SerialException as se:
            # printer unavailable — still return ok so UX isn't broken
            return jsonify({'status': 'ok', 'warning': str(se)}), 200

        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
