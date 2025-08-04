
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from config import Config
from models import Station_dme, Station_dvor, Transmission_dme, Transmission_dvor, User, db, Station, Transmission
from datetime import datetime
import io
import csv
import plotly.graph_objs as go
import plotly.io as pio
from flask_migrate import Migrate
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash
from collections import Counter, defaultdict
from operator import attrgetter

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


@app.route('/ground-check')
@login_required
def ground_check():
    return render_template('ground_check.html', title='Ground Check')




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

    # Data transform
    dates = [row.tanggal.strftime('%Y-%m-%d') for row in data]
    tx1_power = [row.tx1_power for row in data]
    tx2_power = [row.tx2_power for row in data]
    tx1_mod = [row.tx1_mod for row in data]
    tx2_mod = [row.tx2_mod for row in data]
    tx1_swr = [str(row.tx1_swr).lower() for row in data]
    tx2_swr = [str(row.tx2_swr).lower() for row in data]

    # === Line Chart Power ===
    fig_power = go.Figure()
    fig_power.add_trace(go.Scatter(x=dates, y=tx1_power, mode='lines+markers', name='TX1 Power'))
    fig_power.add_trace(go.Scatter(x=dates, y=tx2_power, mode='lines+markers', name='TX2 Power'))
    fig_power.update_layout(title='Power Output TX1 & TX2', xaxis_title='Tanggal', yaxis_title='Watt')
    chart_power = pio.to_html(fig_power, full_html=False)

    # === Line Chart Mod% ===
    fig_mod = go.Figure()
    fig_mod.add_trace(go.Scatter(x=dates, y=tx1_mod, mode='lines+markers', name='TX1 Mod%'))
    fig_mod.add_trace(go.Scatter(x=dates, y=tx2_mod, mode='lines+markers', name='TX2 Mod%'))
    fig_mod.update_layout(title='Modulasi TX1 & TX2', xaxis_title='Tanggal', yaxis_title='Modulasi (%)')
    chart_mod = pio.to_html(fig_mod, full_html=False)

    # === Pie Chart SWR ===
    swr_all = tx1_swr + tx2_swr
    swr_normal = sum(1 for s in swr_all if '1.5' in s or 'normal' in s or 'ok' in s)
    swr_not_normal = len(swr_all) - swr_normal
    fig_swr = go.Figure(data=[go.Pie(labels=["Normal", "Tidak Normal"], values=[swr_normal, swr_not_normal], hole=0.4)])
    fig_swr.update_layout(title="SWR Normal vs Tidak Normal")
    chart_swr = pio.to_html(fig_swr, full_html=False)

    # === Grouped Bar TX1 vs TX2 ===
    fig_grouped = go.Figure()
    fig_grouped.add_trace(go.Bar(x=dates, y=tx1_power, name='TX1 Power'))
    fig_grouped.add_trace(go.Bar(x=dates, y=tx2_power, name='TX2 Power'))
    fig_grouped.update_layout(barmode='group', title="Perbandingan TX1 vs TX2 per Tanggal", xaxis_title="Tanggal", yaxis_title="Watt")
    chart_grouped = pio.to_html(fig_grouped, full_html=False)

    # === Rata-rata Power & Mod% per Stasiun ===
    avg_by_station = defaultdict(lambda: {'tx1_power': [], 'tx2_power': [], 'tx1_mod': [], 'tx2_mod': []})
    for row in data:
        key = row.nama_stasiun
        avg_by_station[key]['tx1_power'].append(row.tx1_power)
        avg_by_station[key]['tx2_power'].append(row.tx2_power)
        avg_by_station[key]['tx1_mod'].append(row.tx1_mod)
        avg_by_station[key]['tx2_mod'].append(row.tx2_mod)

    station_labels = []
    avg_tx1_power = []
    avg_tx2_power = []
    avg_tx1_mod = []
    avg_tx2_mod = []

    for station, values in avg_by_station.items():
        station_labels.append(station)
        avg_tx1_power.append(sum(values['tx1_power']) / len(values['tx1_power']))
        avg_tx2_power.append(sum(values['tx2_power']) / len(values['tx2_power']))
        avg_tx1_mod.append(sum(values['tx1_mod']) / len(values['tx1_mod']))
        avg_tx2_mod.append(sum(values['tx2_mod']) / len(values['tx2_mod']))

    fig_avg_power = go.Figure()
    fig_avg_power.add_trace(go.Bar(x=station_labels, y=avg_tx1_power, name='TX1 Power'))
    fig_avg_power.add_trace(go.Bar(x=station_labels, y=avg_tx2_power, name='TX2 Power'))
    fig_avg_power.update_layout(title='Rata-rata Power per Stasiun', barmode='group', xaxis_title='Stasiun', yaxis_title='Watt')
    chart_avg_power = pio.to_html(fig_avg_power, full_html=False)

    fig_avg_mod = go.Figure()
    fig_avg_mod.add_trace(go.Bar(x=station_labels, y=avg_tx1_mod, name='TX1 Mod%'))
    fig_avg_mod.add_trace(go.Bar(x=station_labels, y=avg_tx2_mod, name='TX2 Mod%'))
    fig_avg_mod.update_layout(title='Rata-rata Mod% per Stasiun', barmode='group', xaxis_title='Stasiun', yaxis_title='Modulasi (%)')
    chart_avg_mod = pio.to_html(fig_avg_mod, full_html=False)

    # === Bar Chart PIC Paling Aktif ===
    pic_counter = Counter(row.pic for row in data)
    pic_labels, pic_values = zip(*pic_counter.items()) if pic_counter else ([], [])

    fig_pic = go.Figure()
    fig_pic.add_trace(go.Bar(x=pic_labels, y=pic_values, marker_color='green'))
    fig_pic.update_layout(title='PIC Paling Aktif', xaxis_title='PIC', yaxis_title='Jumlah Cek')
    chart_pic = pio.to_html(fig_pic, full_html=False)

    # === Summary Teks ===
    summary = {
        'power_summary': f"TX1 rata-rata {sum(tx1_power)/len(tx1_power):.2f} W dan TX2 rata-rata {sum(tx2_power)/len(tx2_power):.2f} W" if tx1_power and tx2_power else "Tidak ada data Power",
        'mod_summary': f"TX1 Mod% rata-rata {sum(tx1_mod)/len(tx1_mod):.2f}% dan TX2 rata-rata {sum(tx2_mod)/len(tx2_mod):.2f}%" if tx1_mod and tx2_mod else "Tidak ada data Mod%",
        'swr_summary': f"{swr_normal} Normal, {swr_not_normal} Tidak Normal dari total {len(swr_all)} entri",
        'pic_summary': f"PIC paling aktif: {pic_labels[pic_values.index(max(pic_values))]} dengan {max(pic_values)} kali pengecekan" if pic_labels else "Tidak ada data PIC"
    }

    # Tahun, Bulan, Tanggal
    years = sorted(set(row.tanggal.year for row in Transmission.query.all()))

    return render_template(
        'vhf/dashboard.html',
        data=data,
        chart_power=chart_power,
        chart_mod=chart_mod,
        chart_swr=chart_swr,
        chart_grouped=chart_grouped,
        chart_avg_power=chart_avg_power,
        chart_avg_mod=chart_avg_mod,
        chart_pic=chart_pic,
        stations=stations,
        selected_station_id=selected_station_id,
        selected_year=selected_year,
        selected_month=selected_month,
        selected_day=selected_day,
        years=years,
        summary=summary
    )

from collections import defaultdict
import calendar

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


