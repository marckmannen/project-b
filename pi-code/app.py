from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_mysqldb import MySQL
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'change-me-to-a-random-string')

# MySQL configuration from environment variables
app.config['MYSQL_HOST'] = os.getenv('DB_HOST', 'localhost')
app.config['MYSQL_USER'] = os.getenv('DB_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('DB_PASSWORD', '')
app.config['MYSQL_DB'] = os.getenv('DB_NAME', 'medicine_vault')
app.config['MYSQL_PORT'] = int(os.getenv('DB_PORT', 3306))
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

# Only table the admin dashboard may query (read-only)
ALLOWED_ADMIN_TABLE = 'orders'

@app.route('/')
def index():
    return render_template('index.html')


# ── API: Health check / connection test ──
@app.route('/api/db-status')
def db_status():
    try:
        cur = mysql.connection.cursor()
        cur.execute('SELECT 1')
        cur.close()
        return jsonify({'status': 'connected'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ── Admin helper ──
def is_admin():
    return session.get('admin_authenticated', False)


# ── Admin pages ──
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


# ── API: Admin orders (read-only, table locked) ──
@app.route('/api/admin/orders', methods=['GET'])
def admin_orders():
    if not is_admin():
        return jsonify({'error': 'Unauthorized'}), 401

    cur = mysql.connection.cursor()
    try:
        cur.execute(f'SELECT * FROM `{ALLOWED_ADMIN_TABLE}` LIMIT 500')
        results = cur.fetchall()
        return jsonify(results), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
