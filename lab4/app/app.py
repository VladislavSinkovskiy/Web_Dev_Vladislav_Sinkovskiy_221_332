from flask import Flask, render_template, session, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from mysqldb import DatabaseConnector
from mysql.connector.errors import DatabaseError
import re

def check_password(password):
    wrong_point = ''
    has_uppercase = False
    has_lowercase = False
    has_digit = False
    if len(password) > 7: 
        if len(password) > 128:
            wrong_point += 'Длина пароля не может быть больше 128 символов. '
    else: 
        wrong_point += 'Длина пароля не может быть меньше 8 символов. '
    for char in password:
        if char.isalnum() or char in '~!@#$%^&*_-+()[]{}><\/|"\',.:;':
            if char.isupper():
                has_uppercase = True
            elif char.islower():
                has_lowercase = True
            elif char.isdigit():
                has_digit = True
        else:
            wrong_point += 'Пароль должен содержать только латинские или кириллические буквы, цифры или ~!@#$%^&*_-+()[]{}><\/|"\',.:; '
    if not has_uppercase:
        wrong_point += 'Пароль должен содержать минимум одну заглавную букву. '
    if not has_lowercase:
        wrong_point += 'Пароль должен содержать минимум одну строчную букву. '
    if not has_digit:
        wrong_point += 'Пароль должен содержать минимум одну цифру. '
    return wrong_point    

# Проверка на пустые поля и соответствие требованиям
def validate_input(login, password, last_name, first_name):
    # Регулярное выражение для логина
    login_pattern = r'^[a-zA-Z0-9]{5,}$'

    # Регулярное выражение для пароля
    password_pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d~!@#$%^&*_+\[\]{}><\/\\|"\'.,:;-]{8,128}$'

    errors = {}

    if login is None:
        errors['login'] = "Поле не может быть пустым"
    elif not re.match(login_pattern, login):
        errors['login'] = "Логин должен состоять только из латинских букв и цифр и иметь длину не менее 5 символов"

    if password is None:
        errors['password'] = "Поле не может быть пустым"
    elif not re.match(password_pattern, password):
        errors['password'] = """Пароль должен удовлетворять следующим требованиям:
        - не менее 8 символов;
        - не более 128 символов;
        - как минимум одна заглавная и одна строчная буква;
        - только латинские или кириллические буквы;
        - как минимум одна цифра;
        - только арабские цифры;
        - без пробелов.
        """

    if last_name is None:
        errors['last_name'] = "Поле не может быть пустым"

    if first_name is None:
        errors['first_name'] = "Поле не может быть пустым"

    return errors

app = Flask(__name__)
application = app

app.config.from_pyfile("config.py")
login_manager = LoginManager()
login_manager.login_view = 'enter'
login_manager.login_message = 'Пожалуйста, авторизуйтесь.'
login_manager.login_message_category = 'warning'
login_manager.init_app(app)
db = DatabaseConnector(app)

class User(UserMixin):
    def __init__(self, login, user_id):
        self.login = login
        self.id = user_id
        
@login_manager.user_loader
def load_user(user_id):
    cnx = db.connect()
    with cnx.cursor(named_tuple=True) as cursor:
        cursor = cnx.cursor(named_tuple=True)
        cursor.execute("SELECT id, login FROM users where id = %s", (user_id,))
        user_data = cursor.fetchone()
    if user_data is not None:
        return User(user_data.login, user_data.id)
    return None

@app.route('/')
def index():
    cnx = db.connect()

    with cnx.cursor(named_tuple=True) as cursor:
        cursor.execute("SELECT users.*, roles.name AS role_name FROM users LEFT JOIN roles ON users.role_id = roles.id")
        users_list = cursor.fetchall()

    return render_template('index.html', users_list=users_list)

@app.route('/enter', methods=['post', 'get'])
def enter():
    massage=''
    if request.method == 'POST':
        user_login = request.form['login']
        user_password = request.form['password']
        check_remember = True if request.form.get('user_remember') else False 
        cnx = db.connect()
        with cnx.cursor(named_tuple=True) as cursor:
            query = "SELECT login, id FROM users where login = %s and password_hash = SHA2(%s, 256)"
            print(query)
            cursor.execute(query, (user_login, user_password))
            print(cursor.statement)
            user_data = cursor.fetchone()
        if user_data is not None:
            login_user(User(user_data.login, user_data.id), remember=check_remember)
            flash("Вход выполнен успешно", "success")      
            return redirect(request.args.get('next', url_for('index')))
        massage = 'Введены неверные данные'
        flash(massage, "danger")
    return render_template('enter.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/users/new', methods=['GET', 'POST'])
def new_user():
    params_dict = {}

    errors = {}

    if request.method == 'POST':
        params_dict = {
            'last_name': request.form['last_name'], 
            'first_name': request.form['first_name'],
            'middle_name': request.form['middle_name'],
            'login': request.form['login'],
            'password': request.form['password'],\
            'role_id': request.form['role_id']
        }

        for key in params_dict:
            if params_dict[key].strip() == '':
                params_dict[key] = None

        answer = validate_input(
            params_dict['login'], 
            params_dict['password'], 
            params_dict['last_name'], 
            params_dict['first_name']
        )

        if len(answer) != 0:
            for key, value in answer.items():
                errors[key] = value

        try:
            cnx = db.connect()

            with cnx.cursor(named_tuple=True) as cursor:
                query = ('INSERT INTO users ('
                'last_name, first_name, middle_name, login, password_hash, role_id) '
                'VALUES (%(last_name)s, %(first_name)s, '
                '%(middle_name)s, %(login)s, SHA2(%(password)s, 256), %(role_id)s)')

                cursor.execute(query, params_dict)

                cnx.commit()

                flash('Пользователь был успешно добавлен', category = 'success')

                return redirect(url_for('index'))
        except DatabaseError:
            flash('Введены некоректные данные', category = 'danger')

            cnx.rollback()

    return render_template('new_user.html', data=params_dict, errors=errors, roles=load_roles())

@app.route('/users/<int:user_id>/show_user', methods=['GET', 'POST'])
def show_user(user_id):
    cnx = db.connect()

    with cnx.cursor(named_tuple=True) as cursor:
        query = (
            "SELECT users.id, users.login, users.last_name, users.first_name, users.middle_name, "
            "roles.name AS role_name FROM users LEFT JOIN roles ON users.role_id = roles.id WHERE users.id = %s"
        )

        cursor.execute(query, (user_id, ))
        user_info = cursor.fetchall()

    return render_template('show_user.html', user_info=user_info)

@app.route('/user/<int:user_id>/change_password', methods=['GET', 'POST'])
@login_required
def change_password(user_id):
    wrong_params = []
    wrong_password = ''
    if request.method == 'POST':
        old_password = request.form['oldpassword'] or wrong_params.append('none_old_password')
        new_password = request.form['newpassword'] or wrong_params.append('none_new_password')
        repeat_password = request.form['repeatpassword'] or wrong_params.append('none_repeat_password')
        # print(wrong_params)
        if wrong_params:
            # flash('Заполните все поля.', 'danger')
            return render_template('change_password.html', wrong_params = wrong_params)

        query = 'SELECT login FROM users WHERE id = %s and password_hash = SHA2(%s, 256);'
        with db.connect().cursor(named_tuple=True) as cursor:
            cursor.execute(query, (user_id, old_password))
            user = cursor.fetchone()

        if new_password:
            wrong_password = check_password(new_password)
            if wrong_password:
                wrong_params.append('incorrect_new_password')

        if new_password != repeat_password:
            wrong_params.append('repeat_password')

        if user and not wrong_params:
            query = 'UPDATE users SET password_hash = SHA2(%s, 256) WHERE id=%s;'
            try:
                with db.connect().cursor(named_tuple=True) as cursor:
                    cursor.execute(query, (new_password, user_id))
                    db.connect().commit()
                    flash('Пароль успешно изменён.', 'success')
                    return redirect(url_for('index'))
            except DatabaseError:
                db.connect().rollback()
                flash('При сохранении данных возникла ошибка.', 'danger')
        elif not user:
            wrong_params.append('old_password')

    return render_template('change_password.html', wrong_params = wrong_params, wrong_password = wrong_password)

@app.route('/users/<int:user_id>/update_user', methods=['GET', 'POST'])
def update_user(user_id):
    data = {}
    if request.method == 'GET':
        try:
            cnx = db.connect()
            with cnx.cursor(named_tuple=True) as cursor:
                query = ("SELECT * FROM users WHERE id = %s")
                cursor.execute(query, (user_id,))
                data = cursor.fetchone()
            if data is None:
                flash("Пользователь не найден", category = 'info')
                return redirect(url_for('users'))
        except DatabaseError:
            flash('Возникла ошибка про обращении к БД!', category = 'danger')
            return redirect(url_for('index'))
    elif request.method == 'POST':
        data = {
            "id": user_id,
            'last_name': request.form['last_name'], 
            'first_name': request.form['first_name'],
            'middle_name': request.form['middle_name'],
            'role_id': request.form['role_id']
        }
        for key in data:
            if key != 'id' and data[key].strip() == '':
                data[key] = None
        try:
            cnx = db.connect()

            with cnx.cursor(named_tuple=True) as cursor:
                query = ("UPDATE users SET last_name = %(last_name)s, "
                          "first_name = %(first_name)s, middle_name = %(middle_name)s, "
                           "role_id = %(role_id)s WHERE id = %(id)s")
                cursor.execute(query, data)
                cnx.commit()

                flash('Пользователь был успешно изменён', category = 'success')
                return redirect(url_for('index'))
        except DatabaseError:
            flash('Введены некоректные данные', category = 'danger')
            cnx.rollback()

    return render_template("update_user.html", data=data, roles=load_roles())

@app.route('/users/<int:user_id>/delete_user', methods=['GET', 'POST'])
def delete_user(user_id):
    try:
        with db.connect().cursor(named_tuple=True) as cursor:
            cursor.execute('DELETE FROM users WHERE users.id=%s;', (user_id,))
            db.connect().commit()
            print(cursor.statement)
        flash('Пользователь успешно удален.', 'success')
    except DatabaseError:
        db.connection().rollback()
        flash('При удалении пользователя возникла ошибка.', 'danger')
    return redirect(url_for('index'))

def load_roles():
    cnx = db.connect()

    with cnx.cursor(named_tuple=True) as cursor:
        cursor.execute('SELECT id, name FROM roles')

        roles = cursor.fetchall()

    return roles
