# app.py — Lapisan 2: Server Flask + SQLite

# Sistem Pakar Distilasi Minyak Kayu Putih

# Mode: Tanpa sensor fisik (simulasi manual + auto-generate)



from flask import Flask, request, jsonify, render_template

import sqlite3, random, time, os

from datetime import datetime



app = Flask(__name__)

DB_PATH = 'data_sensor.db'



# ─────────────────────────────────────────────

# DATABASE SETUP

# ─────────────────────────────────────────────



def init_db():

    conn = sqlite3.connect(DB_PATH)

    c = conn.cursor()

    c.execute('''

        CREATE TABLE IF NOT EXISTS log_sensor (

            id          INTEGER PRIMARY KEY AUTOINCREMENT,

            waktu       TEXT    DEFAULT (datetime('now','localtime')),

            suhu_prod   REAL,

            suhu_cool   REAL,

            ph          REAL,

            tds         REAL,

            status      TEXT,

            rules_aktif TEXT,

            sumber      TEXT DEFAULT 'manual'

        )

    ''')

    conn.commit()

    conn.close()



def get_db():

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    return conn



# ─────────────────────────────────────────────

# SISTEM PAKAR — FORWARD CHAINING

# ─────────────────────────────────────────────



RULES = {

    'R01': {'kondisi': 'Suhu produksi normal (90–105°C)',       'aksi': 'Lanjutkan proses'},

    'R02': {'kondisi': 'Suhu produksi terlalu rendah (<90°C)',  'aksi': 'Naikkan suhu pemanas'},

    'R03': {'kondisi': 'Suhu produksi tinggi (105–112°C)',      'aksi': 'Kurangi intensitas pemanas'},

    'R04': {'kondisi': 'Suhu produksi kritis (>112°C)',         'aksi': 'MATIKAN PEMANAS SEGERA'},

    'R05': {'kondisi': 'Suhu pendingin normal (20–35°C)',       'aksi': 'Pendinginan optimal'},

    'R06': {'kondisi': 'Suhu pendingin terlalu rendah (<20°C)', 'aksi': 'Kurangi aliran air dingin'},

    'R07': {'kondisi': 'Suhu pendingin tinggi (>35°C)',         'aksi': 'Tingkatkan aliran air pendingin'},

    'R08': {'kondisi': 'pH normal (5.5–7.0)',                   'aksi': 'Kualitas distilat baik'},

    'R09': {'kondisi': 'pH terlalu asam (<5.5)',                'aksi': 'Periksa kontaminasi asam'},

    'R10': {'kondisi': 'pH terlalu basa (>7.0)',                'aksi': 'Periksa kontaminasi basa'},

    'R11': {'kondisi': 'TDS normal (50–300 ppm)',               'aksi': 'Kemurnian distilat baik'},

    'R12': {'kondisi': 'TDS sangat rendah (<50 ppm)',           'aksi': 'Distilat sangat murni / sensor error'},

    'R13': {'kondisi': 'TDS tinggi (300–500 ppm)',              'aksi': 'Kemurnian menurun, periksa proses'},

    'R14': {'kondisi': 'TDS kritis (>500 ppm)',                 'aksi': 'HENTIKAN — kemurnian sangat buruk'},

}



def forward_chaining(d):

    sp   = float(d.get('suhu_prod', 0))

    sc   = float(d.get('suhu_cool', 0))

    ph   = float(d.get('ph', 7))

    tds  = float(d.get('tds', 0))



    rules_aktif = []

    status = 'normal'



    # Evaluasi suhu produksi

    if sp < 90:

        rules_aktif.append('R02'); status = 'anomali'

    elif sp > 112:

        rules_aktif.append('R04'); status = 'kritis'

    elif sp > 105:

        rules_aktif.append('R03')

        if status == 'normal': status = 'anomali'

    else:

        rules_aktif.append('R01')



    # Evaluasi suhu pendingin

    if sc < 20:

        rules_aktif.append('R06')

        if status == 'normal': status = 'anomali'

    elif sc > 35:

        rules_aktif.append('R07'); status = 'kritis'

    else:

        rules_aktif.append('R05')



    # Evaluasi pH

    if ph < 5.5:

        rules_aktif.append('R09')

        if status == 'normal': status = 'anomali'

    elif ph > 7.0:

        rules_aktif.append('R10')

        if status == 'normal': status = 'anomali'

    else:

        rules_aktif.append('R08')



    # Evaluasi TDS

    if tds < 50:

        rules_aktif.append('R12')

    elif tds > 500:

        rules_aktif.append('R14'); status = 'kritis'

    elif tds > 300:

        rules_aktif.append('R13')

        if status == 'normal': status = 'anomali'

    else:

        rules_aktif.append('R11')



    rekomendasi = [RULES[r]['aksi'] for r in rules_aktif]

    return status, rules_aktif, rekomendasi



# ─────────────────────────────────────────────

# ROUTES

# ─────────────────────────────────────────────



@app.route('/')

def index():

    return render_template('dashboard.html')



@app.route('/api/sensor', methods=['POST'])

def terima_sensor():

    """Terima data dari ESP32 atau form manual"""

    data = request.get_json()

    if not data:

        return jsonify({'error': 'Data tidak valid'}), 400



    status, rules, rekomendasi = forward_chaining(data)

    sumber = data.get('sumber', 'manual')



    conn = get_db()

    conn.execute('''

        INSERT INTO log_sensor (suhu_prod, suhu_cool, ph, tds, status, rules_aktif, sumber)

        VALUES (?, ?, ?, ?, ?, ?, ?)

    ''', (data.get('suhu_prod'), data.get('suhu_cool'),

          data.get('ph'), data.get('tds'),

          status, ','.join(rules), sumber))

    conn.commit()



    # Ambil ID terakhir

    row = conn.execute('SELECT last_insert_rowid() as id').fetchone()

    last_id = row['id']

    conn.close()



    return jsonify({

        'success': True,

        'id': last_id,

        'status': status,

        'rules': rules,

        'rekomendasi': rekomendasi

    }), 201



@app.route('/api/simulate', methods=['POST'])

def auto_simulate():

    """Generate data sensor acak (realistis untuk distilasi kayu putih)"""

    mode = request.json.get('mode', 'normal') if request.json else 'normal'



    if mode == 'normal':

        data = {

            'suhu_prod': round(random.uniform(92, 104), 1),

            'suhu_cool': round(random.uniform(22, 33), 1),

            'ph':        round(random.uniform(5.8, 6.8), 2),

            'tds':       round(random.uniform(80, 250), 1),

            'sumber':    'simulator'

        }

    elif mode == 'anomali':

        data = {

            'suhu_prod': round(random.uniform(106, 111), 1),

            'suhu_cool': round(random.uniform(33, 38), 1),

            'ph':        round(random.uniform(4.8, 5.4), 2),

            'tds':       round(random.uniform(310, 490), 1),

            'sumber':    'simulator'

        }

    else:  # kritis

        data = {

            'suhu_prod': round(random.uniform(113, 120), 1),

            'suhu_cool': round(random.uniform(38, 45), 1),

            'ph':        round(random.uniform(3.5, 4.5), 2),

            'tds':       round(random.uniform(510, 700), 1),

            'sumber':    'simulator'

        }



    status, rules, rekomendasi = forward_chaining(data)



    conn = get_db()

    conn.execute('''

        INSERT INTO log_sensor (suhu_prod, suhu_cool, ph, tds, status, rules_aktif, sumber)

        VALUES (?, ?, ?, ?, ?, ?, ?)

    ''', (data['suhu_prod'], data['suhu_cool'],

          data['ph'], data['tds'],

          status, ','.join(rules), data['sumber']))

    conn.commit()

    conn.close()



    return jsonify({

        'success': True,

        'data': data,

        'status': status,

        'rules': rules,

        'rekomendasi': rekomendasi

    })



@app.route('/api/log')

def get_log():

    """Ambil data log terbaru"""

    limit = request.args.get('limit', 50, type=int)

    conn = get_db()

    rows = conn.execute(

        'SELECT * FROM log_sensor ORDER BY id DESC LIMIT ?', (limit,)

    ).fetchall()

    conn.close()

    return jsonify([dict(r) for r in rows])



@app.route('/api/latest')

def get_latest():

    """Ambil 1 data terbaru untuk gauge realtime"""

    conn = get_db()

    row = conn.execute(

        'SELECT * FROM log_sensor ORDER BY id DESC LIMIT 1'

    ).fetchone()

    conn.close()

    return jsonify(dict(row) if row else {})



@app.route('/api/stats')

def get_stats():

    """Statistik ringkasan"""

    conn = get_db()

    total   = conn.execute('SELECT COUNT(*) as n FROM log_sensor').fetchone()['n']

    normal  = conn.execute("SELECT COUNT(*) as n FROM log_sensor WHERE status='normal'").fetchone()['n']

    anomali = conn.execute("SELECT COUNT(*) as n FROM log_sensor WHERE status='anomali'").fetchone()['n']

    kritis  = conn.execute("SELECT COUNT(*) as n FROM log_sensor WHERE status='kritis'").fetchone()['n']

    conn.close()

    return jsonify({'total': total, 'normal': normal, 'anomali': anomali, 'kritis': kritis})



@app.route('/api/clear', methods=['DELETE'])

def clear_log():

    """Hapus semua log (untuk testing)"""

    conn = get_db()

    conn.execute('DELETE FROM log_sensor')

    conn.commit()

    conn.close()

    return jsonify({'success': True, 'message': 'Semua log dihapus'})



# ─────────────────────────────────────────────

# MAIN & INISIALISASI (Disiapkan untuk Railway)

# ─────────────────────────────────────────────



# Inisialisasi DB di luar blok if __name__ agar dieksekusi oleh WSGI server (seperti Gunicorn) di Railway

init_db()



if __name__ == '__main__':

    # Membaca port yang diberikan oleh environment Railway, fallback ke 5000 jika dijalankan lokal

    port = int(os.environ.get("PORT", 5000))

    print("=" * 50)

    print("  SISTEM PAKAR DISTILASI MINYAK KAYU PUTIH")

    print("=" * 50)

    # Debug wajib False untuk keamanan di server production

    app.run(host='0.0.0.0', port=port, debug=False)