import os
from config import DevelopmentConfig  # или ProductionConfig
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)  # Загружаем конфигурацию

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Модели
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    theme_dark = db.Column(db.Boolean, default=False)
    folders = db.relationship('Folder', backref='owner', lazy=True, cascade='all, delete-orphan')

class Folder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('folder.id'))
    children = db.relationship('Folder', backref=db.backref('parent', remote_side=[id]))
    files = db.relationship('File', backref='folder', lazy=True, cascade='all, delete-orphan')

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    storage_path = db.Column(db.String(300), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey('folder.id'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Создаем папку для загрузок
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Вспомогательная функция для проверки разрешенных расширений
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 
                         'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'mp3', 
                         'mp4', 'avi', 'mov', 'webp', 'exe', 'odt', 'ods',
                         'iso', 'ovpn', 'msi' }
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Маршруты
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard', folder_id=None))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard', folder_id=None))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard', folder_id=None))
        flash('Неверное имя пользователя или пароль', 'error')
    
    return render_template('login.html', dark_theme=False)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard', folder_id=None))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Имя пользователя уже занято', 'error')
        else:
            new_user = User(
                username=username,
                password_hash=generate_password_hash(password)
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('dashboard', folder_id=None))
    
    return render_template('register.html', dark_theme=False)

@app.route('/dashboard')
@app.route('/dashboard/<int:folder_id>')
@login_required
def dashboard(folder_id=None):
    current_folder = Folder.query.get(folder_id) if folder_id else None
    
    # Проверка прав доступа
    if current_folder and current_folder.user_id != current_user.id:
        abort(403)
    
    # Получаем хлебные крошки
    breadcrumbs = []
    if current_folder:
        parent = current_folder.parent
        while parent:
            breadcrumbs.insert(0, parent)
            parent = parent.parent
    
    # Получаем содержимое текущей папки
    folders = Folder.query.filter_by(
        user_id=current_user.id,
        parent_id=folder_id
    ).all()
    
    files = File.query.filter_by(
        user_id=current_user.id,
        folder_id=folder_id
    ).all()
    
    return render_template(
        'dashboard.html',
        folders=folders,
        files=files,
        current_folder=current_folder,
        breadcrumbs=breadcrumbs,
        dark_theme=current_user.theme_dark
    )

@app.route('/create_folder', methods=['POST'])
@login_required
def create_folder():
    folder_name = request.form.get('folder_name')
    parent_id = request.form.get('parent_id', type=int) or None
    
    if not folder_name:
        flash('Введите название папки', 'error')
        return redirect(url_for('dashboard', folder_id=parent_id))
    
    # Проверка прав на родительскую папку
    if parent_id and Folder.query.get(parent_id).user_id != current_user.id:
        abort(403)
    
    new_folder = Folder(
        name=folder_name,
        user_id=current_user.id,
        parent_id=parent_id
    )
    db.session.add(new_folder)
    db.session.commit()
    
    flash('Папка успешно создана', 'success')
    return redirect(url_for('dashboard', folder_id=parent_id))

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'files' not in request.files:
        flash('Файлы не выбраны', 'error')
        return redirect(request.referrer)
    
    files = request.files.getlist('files')
    folder_id = request.form.get('folder_id', type=int) or None
    
    if not files or all(file.filename == '' for file in files):
        flash('Файлы не выбраны', 'error')
        return redirect(request.referrer)
    
    if folder_id and Folder.query.get(folder_id).user_id != current_user.id:
        abort(403)
    
    uploaded_count = 0
    for file in files:
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            user_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id))
            os.makedirs(user_upload_dir, exist_ok=True)
            
            # Генерируем уникальное имя файла
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(os.path.join(user_upload_dir, filename)):
                filename = f"{base}_{counter}{ext}"
                counter += 1
            
            filepath = os.path.join(user_upload_dir, filename)
            file.save(filepath)
            
            new_file = File(
                name=filename,
                storage_path=filepath,
                size=os.path.getsize(filepath),
                user_id=current_user.id,
                folder_id=folder_id
            )
            
            db.session.add(new_file)
            uploaded_count += 1
    
    if uploaded_count > 0:
        db.session.commit()
        flash(f'Успешно загружено {uploaded_count} файлов', 'success')
    else:
        flash('Не удалось загрузить файлы. Проверьте формат файлов', 'error')
    
    return redirect(request.referrer)

@app.route('/download/<int:file_id>')
@login_required
def download_file(file_id):
    file = File.query.get_or_404(file_id)
    if file.user_id != current_user.id:
        abort(403)
    
    return send_from_directory(
        os.path.dirname(file.storage_path),
        os.path.basename(file.storage_path),
        as_attachment=True
    )

@app.route('/delete_file/<int:file_id>')
@login_required
def delete_file(file_id):
    file = File.query.get_or_404(file_id)
    if file.user_id != current_user.id:
        abort(403)
    
    try:
        os.remove(file.storage_path)
    except Exception as e:
        app.logger.error(f"Ошибка удаления файла: {e}")
    
    db.session.delete(file)
    db.session.commit()
    flash('Файл успешно удален', 'success')
    return redirect(request.referrer)

@app.route('/delete_folder/<int:folder_id>')
@login_required
def delete_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    if folder.user_id != current_user.id:
        abort(403)
    
    parent_id = folder.parent_id
    
    # Рекурсивное удаление файлов
    def delete_folder_contents(folder):
        for file in folder.files:
            try:
                os.remove(file.storage_path)
            except Exception as e:
                app.logger.error(f"Ошибка удаления файла: {e}")
            db.session.delete(file)
        
        for child in folder.children:
            delete_folder_contents(child)
            db.session.delete(child)
    
    delete_folder_contents(folder)
    db.session.delete(folder)
    db.session.commit()
    
    flash('Папка и её содержимое удалены', 'success')
    return redirect(url_for('dashboard', folder_id=parent_id))

@app.route('/toggle_theme', methods=['POST'])
@login_required
def toggle_theme():
    current_user.theme_dark = not current_user.theme_dark
    db.session.commit()
    return jsonify({'success': True, 'dark_theme': current_user.theme_dark})

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Инициализация БД
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=80)