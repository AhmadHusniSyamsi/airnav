from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash
from models import db, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Cek apakah username sudah ada
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username sudah terdaftar. Gunakan username lain.')
            return redirect(url_for('auth.register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registrasi berhasil! Silakan login.')
        return redirect(url_for('login'))

    return render_template('register.html')
