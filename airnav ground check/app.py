
import csv
import io
from collections import Counter, defaultdict
from datetime import datetime
from operator import attrgetter

import plotly.graph_objs as go
import plotly.io as pio
from flask import (Flask, flash, redirect, render_template, request, send_file,
                   url_for)
from flask_login import (LoginManager, current_user, login_required,
                         login_user, logout_user)
from flask_migrate import Migrate
from werkzeug.security import check_password_hash

from config import Config
from models import (Station, Station_dme, Station_dvor, Transmission,
                    Transmission_dme, Transmission_dvor, User, db)

app = Flask(__name__)
app.secret_key = 'rahasia'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/data_vhf'
app.config.from_object(Config)

# Register untuk Blueprintnya
from dvor_routes import dvor_bp

app.register_blueprint(dvor_bp)


from dme_routes import dme_bp

app.register_blueprint(dme_bp)

from radar_routes import radar_bp

app.register_blueprint(radar_bp)

from ils_route import ils_bp

app.register_blueprint(ils_bp)

from auth_routes import auth_bp

app.register_blueprint(auth_bp)

db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('main_dashboard'))
    return redirect(url_for('login'))

@app.route('/index')
def index():
    return render_template('index.html', title='Beranda')


@app.route('/ground-check')
@login_required
def ground_check():
    return render_template('ground_check.html', title='Ground Check', data=data_rows)




@app.route('/main_dashboard')
@login_required
def main_dashboard():
    return render_template('main_dashboard.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('home'))
        flash('Username atau password salah.','danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/station_list')
@login_required
def station_list():
    stations = Station.query.all()
    return render_template('vhf/station_list.html', stations=stations)

@app.route('/station/add', methods=['GET', 'POST'])
@login_required
def add_station():
    if request.method == 'POST':
        nama = request.form['nama_stasiun']
        frek = request.form['frekuensi']
        new_station = Station(nama_stasiun=nama, frekuensi=frek)
        db.session.add(new_station)
        db.session.commit()
        return redirect(url_for('add_transmission', nama_stasiun=new_station.nama_stasiun))
    return render_template('vhf/station_form.html')

@app.route('/transmission/add/<path:nama_stasiun>', methods=['GET', 'POST'])
@login_required
def add_transmission(nama_stasiun):
    station = Station.query.filter_by(nama_stasiun=nama_stasiun).first_or_404()

    if request.method == 'POST':
        tx = Transmission(
            station_id=station.id,
            tx1_power=float(request.form.get('tx1_power') or 0),
            tx1_swr=request.form.get('tx1_swr'),
            tx1_mod=float(request.form.get('tx1_mod') or 0),
            tx2_power=float(request.form.get('tx2_power') or 0),
            tx2_swr=request.form.get('tx2_swr'),
            tx2_mod=float(request.form.get('tx2_mod') or 0),
            tanggal=datetime.strptime(request.form['tanggal'], '%Y-%m-%d'),
            pic=request.form['pic']
        )
        db.session.add(tx)
        db.session.commit()

        flash('Data berhasil disimpan.' 'Success')

        action = request.form.get('action')

        if action == 'save_and_add':
            return redirect(url_for('add_transmission', nama_stasiun=station.nama_stasiun))
        else:
            return redirect(url_for('view_data'))

    return render_template('vhf/transmission_form.html', station=station, tx=None)


@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    stations = Station.query.all()
    selected_station_id = request.form.get('station_id')
    selected_year = request.form.get('year', type=int)
    selected_month = request.form.get('month', type=int)
    selected_day = request.form.get('day', type=int)

    query = Transmission.query.join(Station)
    if selected_station_id:
        query = query.filter(Transmission.station_id == selected_station_id)
    if selected_year:
        query = query.filter(db.extract('year', Transmission.tanggal) == selected_year)
    if selected_month:
        query = query.filter(db.extract('month', Transmission.tanggal) == selected_month)
    if selected_day:
        query = query.filter(db.extract('day', Transmission.tanggal) == selected_day)

    data = query.add_columns(
        Station.nama_stasiun, Station.frekuensi,
        Transmission.tx1_power, Transmission.tx1_swr, Transmission.tx1_mod,
        Transmission.tx2_power, Transmission.tx2_swr, Transmission.tx2_mod,
        Transmission.tanggal, Transmission.pic
    ).order_by(Transmission.tanggal).all()
    
    
    
data_rows = []

@app.route('/', methods=['GET', 'POST'])
def performance_curve():
    if request.method == 'POST':
        new_row = {
            'jarak': request.form['jarak'],
            'degree': request.form['degree'],
            'tx1_ddm': request.form['tx1_ddm'],
            'tx1_sum': request.form['tx1_sum'],
            'tx1_mod90': request.form['tx1_mod90'],
            'tx1_mod150': request.form['tx1_mod150'],
            'tx1_rf': request.form['tx1_rf'],
            'tx2_ddm': request.form['tx2_ddm'],
            'tx2_sum': request.form['tx2_sum'],
            'tx2_mod90': request.form['tx2_mod90'],
            'tx2_mod150': request.form['tx2_mod150'],
            'tx2_rf': request.form['tx2_rf'],
        }
        data_rows.append(new_row)
        return redirect(url_for('ground_check'))

    return render_template('ground_check.html', data=data_rows)

import calendar
from collections import defaultdict


@app.route('/data')
@login_required
def view_data():
    stations = Station.query.order_by(Station.nama_stasiun).all()

    grouped_data = []
    for station in stations:
        transmissions = Transmission.query.filter_by(station_id=station.id).all()
        if transmissions:
            # Group by year
            per_year = defaultdict(list)
            for tx in transmissions:
                year = tx.tanggal.year
                per_year[year].append(tx)

            # Urutkan berdasarkan bulan dan tanggal (ascending)
            for year in per_year:
                per_year[year].sort(key=attrgetter('tanggal'))  # ascending order

            # Urutkan tahun dari terbaru ke lama
            sorted_per_year = dict(sorted(per_year.items(), reverse=True))

            grouped_data.append({
                'station': station,
                'per_year': sorted_per_year
            })

    return render_template('vhf/data_table.html', grouped_data=grouped_data)


@app.route('/transmission/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_transmission(id):
    # station
    tx = Transmission.query.get_or_404(id)
    station = Station.query.get_or_404(tx.station_id)
    if request.method == 'POST':
        # station.Stasiun = str(request.form.get('Stasiun')) if request.form.get('Statiun') else None
        # tx.station_id=strrequest.form.getstation.id,
        tx.tx1_power = float(request.form.get('tx1_power')) if request.form.get('tx1_power') else None
        tx.tx1_swr = request.form.get('tx1_swr') or None
        tx.tx1_mod = float(request.form.get('tx1_mod')) if request.form.get('tx1_mod') else None
        tx.tx2_power = float(request.form.get('tx2_power')) if request.form.get('tx2_power') else None
        tx.tx2_swr = request.form.get('tx2_swr') or None
        tx.tx2_mod = float(request.form.get('tx2_mod')) if request.form.get('tx2_mod') else None
        tx.tanggal = datetime.strptime(request.form.get('tanggal'), '%Y-%m-%d')
        tx.pic = request.form.get('pic')
        
        db.session.commit()
        return redirect(url_for('view_data'))
    return render_template('vhf/transmission_form.html', tx=tx, station=station)

@app.route('/transmission/delete/<int:id>', methods=['GET'])
@login_required
def delete_transmission(id):
    tx = Transmission.query.get_or_404(id)
    db.session.delete(tx)
    db.session.commit()
    return redirect(url_for('view_data'))

# @app.route('/station/edit/<path:nama_stasiun>/<float:frekuensi>', methods=['GET', 'POST'])
@app.route('/station/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_station(id):
    station = Station.query.get_or_404(id)
    if request.method == 'POST':
        station.nama_stasiun = request.form['nama_stasiun']
        station.frekuensi = request.form['frekuensi']
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('vhf/station_form.html', station=station)


# # @app.route('/station/delete/<path:nama_stasiun>/<float:frekuensi>', methods=['GET', 'POST'])
@app.route('/station/delete/<int:id>', methods=['GET', 'POST'])
@login_required
def delete_station(id):
    station = Station.query.get_or_404(id)
    Transmission.query.filter_by(station_id=station.id).delete()

    db.session.delete(station)
    db.session.commit()
    return redirect(url_for('station_list'))
    

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/history')
@login_required
def history():
    data = Transmission.query.join(Station).add_columns(
        Transmission.id,
        Station.nama_stasiun,
        Station.frekuensi,
        Transmission.tx1_power,
        Transmission.tx1_mod,
        Transmission.tx2_power,
        Transmission.tx2_mod,
        Transmission.tanggal,
        Transmission.pic
    ).order_by(Transmission.tanggal.desc()).all()

    return render_template('history.html')


@app.route('/export')
@login_required
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Stasiun', 'Frekuensi', 'TX1 Power', 'TX1 SWR', 'TX1 Mod%', 'TX2 Power', 'TX2 SWR', 'TX2 Mod%', 'Tanggal', 'PIC'])

    txs = Transmission.query.join(Station).add_columns(
        Station.nama_stasiun, Station.frekuensi,
        Transmission.tx1_power, Transmission.tx1_swr, Transmission.tx1_mod,
        Transmission.tx2_power, Transmission.tx2_swr, Transmission.tx2_mod,
        Transmission.tanggal, Transmission.pic
    ).all()

    for row in txs:
        writer.writerow([
            row.nama_stasiun, row.frekuensi,
            row.tx1_power, row.tx1_swr, row.tx1_mod,
            row.tx2_power, row.tx2_swr, row.tx2_mod,
            row.tanggal, row.pic
        ])

    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name='data_vhf.csv')

if __name__ == '__main__':
    app.run(debug=True)


#Bagian VCCS

@app.route('/station_list_vccs')
@login_required
def station_list_vccs():
    stations = Station.query.all()
    return render_template('vccs/stationlist_vccs.html', stations=stations)

@app.route('/station_vccs/add', methods=['GET', 'POST'])
@login_required
def add_station_vccs():
    if request.method == 'POST':
        nama = request.form['nama_stasiun']
        frek = request.form['frekuensi']
        new_station = Station(nama_stasiun=nama, frekuensi=frek)
        db.session.add(new_station)
        db.session.commit()
        return redirect(url_for('add_transmission', nama_stasiun=new_station.nama_stasiun))
    return render_template('vccs/stationform_vccs.html')
@app.route('/')
def home():
    return 'Hello from Flask!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


