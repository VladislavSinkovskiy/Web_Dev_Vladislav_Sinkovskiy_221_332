from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from mysql_db import MySQL
import mysql.connector

# Ограничение на список параметров для извлечения
PERMITED_PARAMS = ['login', 'password', 'last_name',
                   'first_name', 'middle_name', 'role_id']
# Список параметров разрешенных для редактирования
EDIT_PARAMS = ['last_name', 'first_name', 'middle_name', 'role_id']

app = Flask(__name__)
# Создаем экземпляр приложения
application = app
# Пишем, чтобы на хостинге всё запускалось

# Нужен секретный ключ, чтобы работать с сессией. Сам ключ генерируем в отдельном файле и импортируем его.
app.config.from_pyfile('config.py')

# Создаем объект класса MySQL
db = MySQL(app)

# Импорт происходит после загрузки БД, чтобы круг не замкнулся
from auth import bp as auth_bp
# Импортируем init_login_manager, чтобы создавался login_manager и передавалось в него приложение
from auth import init_login_manager
# Импортирует декоратор
from auth import permission_check

from visits import bp as visits_bp

# Регистрируем блюпринт авторизации
app.register_blueprint(auth_bp)
# Инициализируем login_manager, чтобы flask_login корректно работал
init_login_manager(app)
# Регистрируем блюпринт посещений
app.register_blueprint(visits_bp)

# # Функция записывает логи посещений сайта в базу данных для каждого выполненного запроса
# Если запрос является статичным, то функция завершает работу без выполнения дополнительных действий
# Декоратор before_request позволяет связать эту функцию с обработкой каждого запроса перед его выполнением
@app.before_request
def loger():
    # Статичные запросы не попадают в таблицу с логами, благодаря нижней конструкции
    # Проверяем, является ли запрашиваемый ресурс статичным файлом
    if request.endpoint == 'static':
        # Если да, то завершаем работу функции без выполнения дополнительных действий
        return

    # Получаем путь запрашиваемого ресурса
    path = request.path
    # Получаем идентификатор пользователя, который выполняет запрос
    user_id = getattr(current_user, 'id', None)
    # Формируем SQL-запрос для записи лога посещения
    query = 'INSERT INTO action_logs(user_id, path) VALUES (%s, %s);'
    try:
        # Выполняем запрос к базе данных через соединение из пула
        # Сursor с параметром named_tuple=True позволяет использовать курсор в качестве именованного кортежа
        with db.connection().cursor(named_tuple=True) as cursor:
            # Выполняем запрос на добавление записи в логи
            cursor.execute(query, (user_id, path))
            # Фиксируем изменения в базе данных
            print(cursor.statement)
            # print(cursor.statement) - ввыводит какой запрос был выполнен в БД
            db.connection().commit()
    # Если произошла ошибка взаимодействия с базой данных
    except mysql.connector.errors.DatabaseError:
        # Откатываем изменения в базе данных до начала выполнения текущей транзакции
        db.connection().rollback()

# Главная страничка
@app.route('/')
def index():
    return render_template('index.html')

# Страничка с пользователями
@app.route('/users')
def users():
    # SQL-запрос к базе данных, вывод всех пользователей
    query = 'SELECT users.*, roles.name AS role_name FROM users LEFT JOIN roles ON roles.id = users.role_id'
    # C помощью with можно не закрывать cursor как делали это в load_user, это будет сделано автоматически
    with db.connection().cursor(named_tuple=True) as cursor:
        # Подставляем в верхний запрос при помощи метода execute(принимает аргумен-запрос, передаем кортеж(tuple) со значениями)
        # кортеж с одним элементом мохдается благодаря ЗАПЯТОЙ на конце, иначе работать не будет
        cursor.execute(query)
        # print(cursor.statement) - ввыводит какой запрос был выполнен в БД
        print(cursor.statement)
        # Метод fetchall() возвращает список с кортежами, если результатов нет, то вернется пустой список
        users_list = cursor.fetchall()
    return render_template('users.html', users_list=users_list)

# Страничка с добавлением пользователя
@app.route('/users/new')
@login_required  # для того, чтобы только авторизованный пользователь мог отправить данные по этому руту
@permission_check('create')
def users_new():
    # if not current_user.can('create'):
    #     flash('Недостаточно прав для выполнения данного действия.', 'warning')
    #     return redirect(url_for('users'))
    roles_list = load_roles()
    return render_template('users_new.html', roles_list=roles_list, user={})

# Функция, которая загружает данные ролей из БД
def load_roles():
    # SQL-запрос к базе данных
    query = 'SELECT * FROM roles'
    # C помощью with можно не закрывать cursor как делали это в load_user, это будет сделано автоматически
    with db.connection().cursor(named_tuple=True) as cursor:
        # Подставляем в верхний запрос при помощи метода execute(принимает аргумен-запрос, передаем кортеж(tuple) со значениями)
        # кортеж с одним элементом мохдается благодаря ЗАПЯТОЙ на конце, иначе работать не будет
        cursor.execute(query)
        # print(cursor.statement) - ввыводит какой запрос был выполнен в БД
        print(cursor.statement)
        # Метод fetchall() возвращает список с кортежами, если результатов нет, то вернется пустой список
        roles = cursor.fetchall()
        return roles

# Функция, которая извлекает из запроса нужные параметры и складывает их в словарь, а затем возвращает его
# В качестве агрумента передается список параметров (params_list), которые мы хотим извлечь из запроса
def extract_params(params_list):
    params_dict = {}
    for param in params_list:
        # params_dict[param] = request.form[param] or None
        params_dict[param] = request.form.get(param, None) or None
        # or None используется для избегания бага с добавлением в БД пустой строки
    return params_dict

# Проверка логина на длину
def check_login_len(login):
    if len(login) < 5:
        message = 'Логин должен иметь длину не менее 5 символов'
    else:
        message = None
    return message

# Проверка, состоит ли пароль только из латинских букв и цифр
def check_login_latin(login):
    message = None
    latin_symb = 'abcdefghijklmnopqrstuvwxyz'
    # Для простоты проверки удаляем из пароля все цифры и пробелы
    login_without_numbers = ''
    for symb in login:
        if (symb.isdigit() == False) and (symb != ' '):
            login_without_numbers = login_without_numbers + symb.lower()  # приводим к одному регистру для сравнения
    # Сам алгоритм проверки
    for symb in login_without_numbers:
        if not (symb in latin_symb):
            message = 'Логин должен состоять только из латинских букв и цифр'
            break
        else:
            message = None
    return message

# Все проверки пароля и вывод сообщения под полем ввода
def all_check_login(login):
    input_class, div_class = '', ''
    bootstrap_class_green = {
        'input_class': 'is-valid', 'div_class': 'valid-feedback'}
    bootstrap_class_red = {'input_class': 'is-invalid',
                           'div_class': 'invalid-feedback'}

    message = None
    # Выполнение всех функций по порядку
    while message == None:
        message = check_login_len(login)
        break
    while message == None:
        message = check_login_latin(login)
        break

    # Вывод сообщения под полем ввода
    if message == None:
        message = 'Логин удовлетворяет всем требованиям'
        input_class = bootstrap_class_green['input_class']
        div_class = bootstrap_class_green['div_class']
    # elif, чтобы по умолчанию не подсвечивалось поле
    elif message == '':
        input_class = ''
        div_class = ''
    else:
        input_class = bootstrap_class_red['input_class']
        div_class = bootstrap_class_red['div_class']

    return input_class, div_class, message

# Сохранение данных нового пользователя
@app.route('/users/create', methods=['POST'])
@login_required  # для того, чтобы только авторизованный пользователь мог отправить данные по этому руту
@permission_check('create')
def create_user():
    # if not current_user.can('create'):
    #     flash('Недостаточно прав для выполнения данного действия.', 'warning')
    #     return redirect(url_for('users'))
    
    input_class, div_class, message = None, None, None
    password_input_class, password_div_class, password_message = None, None, None
    
    # Получение данных из запроса
    params = extract_params(PERMITED_PARAMS)

    input_class, div_class, message = all_check_login(params['login'])
    password_input_class, password_div_class, password_message = all_check_password(params['password'])

    if message and password_message is not None:
        if message == 'Логин удовлетворяет всем требованиям' and password_message == 'Пароль удовлетворяет всем требованиям':
            # Запрос для отправления данных в БД
            # с помощью конструкции %()s подставляем из словаря
            query = 'INSERT INTO users (login, password_hash, last_name, first_name, middle_name, role_id) VALUES (%(login)s, SHA2(%(password)s, 256), %(last_name)s, %(first_name)s, %(middle_name)s, %(role_id)s);'
            # Для перехвата ошибок (если ввели неуникальный логин) оборачиваем выполнение запроса в try
            try:
                # C помощью with можно не закрывать cursor как делали это в load_user, это будет сделано автоматически
                with db.connection().cursor(named_tuple=True) as cursor:
                    # Подставляем в верхний запрос при помощи метода execute(принимает аргумен-запрос, передаем кортеж(tuple) со значениями)
                    cursor.execute(query, params)
                    # .commit() - для окончательного добавления записи в БД
                    db.connection().commit()
                    flash('Обработка данных прошла успешно!', 'success')
            # mysql.connector.errors.DatabaseError - базовый класс для всех ошибок с БД (нарушение целостности, соединения и тд.)
            except mysql.connector.errors.DatabaseError:
                # Если случались ошибка, то идет откатить ти изменения, что были внесены до этого
                db.connection().rollback()  # для этого используется метод rollback()
                flash('При сохранении данных возникла ошибка!', 'danger')
                # передается список ролей для рендеринга
                return render_template('users_new.html', user=params, roles_list=load_roles())
                # user=params, чтобы данный вставлялись в форму в случае ошибки
        else:
            return render_template('users_new.html', user=params, roles_list=load_roles(), input_class=input_class, div_class=div_class, message=message, password_input_class=password_input_class, password_div_class=password_div_class, password_message=password_message)
    return redirect(url_for('users'))

# Страничка для изменения пользователя
@app.route('/users/<int:user_id>/update', methods=['POST'])
@login_required  # для того, чтобы только авторизованный пользователь мог отправить данные по этому руту
@permission_check('edit')
def update_user(user_id):
    # if not current_user.can('edit'):
    #     flash('Недостаточно прав для выполнения данного действия.', 'warning')
    #     return redirect(url_for('users'))
    
    # Получение данных из запроса
    params = extract_params(EDIT_PARAMS)
    params['id'] = user_id

    # # Запрос для отправления данных в БД
    # query = ('UPDATE users SET last_name=%(last_name)s, first_name=%(first_name)s, '
    #          'middle_name=%(middle_name)s, role_id=%(role_id)s WHERE id=%(id)s;')
    # с помощью конструкции %()s подставляем из словаря

    if current_user.can('change_role'):
        # Запрос для отправления данных в БД
        query = ('UPDATE users SET last_name=%(last_name)s, first_name=%(first_name)s, '
                'middle_name=%(middle_name)s, role_id=%(role_id)s WHERE id=%(id)s;')
    else:
        # Удаляем параметр role_id, чтобы пользователь не без прав не мог сменить роль в форме
        del params['role_id']
        # Запрос для отправления данных в БД
        query = ('UPDATE users SET last_name=%(last_name)s, first_name=%(first_name)s, '
                'middle_name=%(middle_name)s WHERE id=%(id)s;')

    # Для перехвата ошибок (если ввели неуникальный логин) оборачиваем выполнение запроса в try
    try:
        # C помощью with можно не закрывать cursor как делали это в load_user, это будет сделано автоматически
        with db.connection().cursor(named_tuple=True) as cursor:
            # Подставляем в верхний запрос при помощи метода execute(принимает аргумен-запрос, передаем кортеж(tuple) со значениями)
            cursor.execute(query, params)
            # .commit() - для окончательного добавления записи в БД
            db.connection().commit()
            flash('Обработка данных прошла успешно!', 'success')
    # mysql.connector.errors.DatabaseError - базовый класс для всех ошибок с БД (нарушение целостности, соединения и тд.)
    except mysql.connector.errors.DatabaseError:
        # Если случались ошибка, то идет откатить ти изменения, что были внесены до этого
        db.connection().rollback()  # для этого используется метод rollback()
        flash('При сохранении данных возникла ошибка.', 'danger')
        # передается список ролей для рендеринга
        return render_template('users_edit.html', user=params, roles_list=load_roles())
        # user=params, чтобы данный вставлялись в форму в случае ошибки
    return redirect(url_for('users'))

# Страничка редактирования с формой
@app.route('/users/<int:user_id>/edit')
@login_required  # для того, чтобы только авторизованный пользователь мог отправить данные по этому руту
@permission_check('edit')
def edit_user(user_id):
    # if not current_user.can('edit'):
    #     flash('Недостаточно прав для выполнения данного действия.', 'warning')
    #     return redirect(url_for('users'))
    
    # SQL-запрос к базе данных, вывод всех пользователей
    query = 'SELECT * FROM users WHERE users.id = %s'
    # C помощью with можно не закрывать cursor как делали это в load_user, это будет сделано автоматически
    with db.connection().cursor(named_tuple=True) as cursor:
        # Подставляем в верхний запрос при помощи метода execute(принимает аргумен-запрос, передаем кортеж(tuple) со значениями)
        # кортеж с одним элементом мохдается благодаря ЗАПЯТОЙ на конце, иначе работать не будет
        cursor.execute(query, (user_id,))
        # print(cursor.statement) - ввыводит какой запрос был выполнен в БД
        print(cursor.statement)
        # Метод fetchone() возвращает либо None, если результат пустой, либо кортеж с найденной записью, если что-то нашлось
        user = cursor.fetchone()
    return render_template('users_edit.html', user=user, roles_list=load_roles())
    # user передает данные пользователя, которые затем мы подставим в html

# Страничка для просмотра пользователя
@app.route('/user/<int:user_id>')
@permission_check('show')
def show_user(user_id):
    # if not current_user.can('show'):
    #     flash('Недостаточно прав для выполнения данного действия.', 'warning')
    #     return redirect(url_for('users'))

    # SQL-запрос к базе данных, вывод всех пользователей
    query = 'SELECT * FROM users WHERE users.id = %s'
    # C помощью with можно не закрывать cursor как делали это в load_user, это будет сделано автоматически
    with db.connection().cursor(named_tuple=True) as cursor:
        # Подставляем в верхний запрос при помощи метода execute(принимает аргумен-запрос, передаем кортеж(tuple) со значениями)
        # кортеж с одним элементом мохдается благодаря ЗАПЯТОЙ на конце, иначе работать не будет
        cursor.execute(query, (user_id,))
        # print(cursor.statement) - ввыводит какой запрос был выполнен в БД
        print(cursor.statement)
        # Метод fetchone() возвращает либо None, если результат пустой, либо кортеж с найденной записью, если что-то нашлось
        user = cursor.fetchone()
    return render_template('users_show.html', user=user)
    # user передает данные пользователя, которые затем мы подставим в html

# Страничка удаления пользователей
@app.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required  # для того, чтобы только авторизованный пользователь мог отправить данные по этому руту
@permission_check('delete')
def delete_user(user_id):
    # if not current_user.can('delete'):
    #     flash('Недостаточно прав для выполнения данного действия.', 'warning')
    #     return redirect(url_for('users'))
    
    # SQL-запрос к базе данных, вывод всех пользователей
    query = 'DELETE FROM users WHERE users.id=%s;'
    # Для перехвата ошибок (если ввели неуникальный логин) оборачиваем выполнение запроса в try
    try:
        # C помощью with можно не закрывать cursor как делали это в load_user, это будет сделано автоматически
        with db.connection().cursor(named_tuple=True) as cursor:
            # Подставляем в верхний запрос при помощи метода execute(принимает аргумен-запрос, передаем кортеж(tuple) со значениями)
            # кортеж с одним элементом мохдается благодаря ЗАПЯТОЙ на конце, иначе работать не будет
            cursor.execute(query, (user_id,))
            # .commit() - для окончательного добавления записи в БД
            db.connection().commit()
            # print(cursor.statement) - ввыводит какой запрос был выполнен в БД
            print(cursor.statement)
        flash('Пользователь успешно удален.', 'success')
    except mysql.connector.errors.DatabaseError:
        db.connection().rollback()
        flash('При удалении пользователя возникла ошибка.', 'danger')
    return redirect(url_for('users'))
    # user передает данные пользователя, которые затем мы подставим в html

# ------------------------------------------------------------------------------------------------

# Проверка пароля на длинну
def check_password_len(password):
    if len(password) < 8 or len(password) > 128:
        message = 'Пароль должен иметь длинну не менее 8 символов и не более 128 символов'
    else:
        message = None
    return message

# Проверка, что есть минимум одна заглавная и одна строчная буква
def check_password_upper_lower(password):
    status_upper = False
    status_lower = False
    for symb in password:
        if symb.isupper():
            status_upper = True
    for symb in password:
        if symb.islower():
            status_lower = True
    if (status_upper == True) and (status_lower == True):
        message = None
    else:
        message = 'В пароле должна присутствовать как минимум одна заглавная и одна строчная буква'
    return message

# Проверка, что ввели латинские или кириллические буквы И спецсимволы ~!?@#$%^&*_-+()[]{}></\|"'.,:;
def check_password_cyrillic_latin_special_symb(password):
    cyrillic_symb = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'
    latin_symb = 'abcdefghijklmnopqrstuvwxyz'
    special_symb = '''~!?@#$%^&*_-+()[]{}></\|"'.,:;'''
    # Для простоты проверки удаляем из пароля все цифры и пробелы
    password_without_numbers = ''
    for symb in password:
        if (symb.isdigit() == False) and (symb != ' '):
            password_without_numbers = password_without_numbers + \
                symb.lower()  # приводим к одному регистру для сравнения
    # Основной алгоритм проверки
    status_symb = True
    for symb in password_without_numbers:
        if not ((symb in cyrillic_symb) or (symb in latin_symb) or (symb in special_symb)):
            status_symb = False
    if status_symb == False:
        message = 'В пароле должны присутствовать латинские или кириллические буквы'
    else:
        message = None
    return message

# Проверка, есть ли в пароле минимальное колличество арабских цифр
def check_password_min_num_of_digit(password):
    status_digit = False
    for symb in password:
        if symb.isdigit():
            status_digit = True
    if status_digit == True:
        message = None
    else:
        message = 'В пароле должна присутствовать как минимум одна цифра'
    return message

# Проверка на наличие пробелов
def check_password_space(password):
    status_space = False
    for symb in password:
        if symb.isspace():
            status_space = True
        else:
            message = None
    if status_space == True:
        message = 'В пароле не должно быть пробелов'
    return message

# Все проверки пароля и вывод сообщения под полем ввода
def all_check_password(password):
    input_class, div_class = '', ''
    bootstrap_class_green = {
        'input_class': 'is-valid', 'div_class': 'valid-feedback'}
    bootstrap_class_red = {'input_class': 'is-invalid',
                           'div_class': 'invalid-feedback'}

    message = None
    # Выполнение всех функций по порядку
    while message == None:
        message = check_password_len(password)
        break
    while message == None:
        message = check_password_min_num_of_digit(password)
        break
    while message == None:
        message = check_password_cyrillic_latin_special_symb(password)
        break
    while message == None:
        message = check_password_upper_lower(password)
        break
    while message == None:
        message = check_password_space(password)
        break

    # Вывод сообщения под полем ввода
    if message == None:
        message = 'Пароль удовлетворяет всем требованиям'
        input_class = bootstrap_class_green['input_class']
        div_class = bootstrap_class_green['div_class']
    # elif, чтобы по умолчанию не подсвечивалось поле
    elif message == '':
        input_class = ''
        div_class = ''
    else:
        input_class = bootstrap_class_red['input_class']
        div_class = bootstrap_class_red['div_class']

    return input_class, div_class, message

# Проверка сходства паролей и вывод сообщения под полем ввода
def password_comparison(new_password, confirm_password, message):
    bootstrap_class_green = {
        'input_class': 'is-valid', 'div_class': 'valid-feedback'}
    bootstrap_class_red = {'input_class': 'is-invalid',
                           'div_class': 'invalid-feedback'}
    confirm_message, confirm_input_class, confirm_div_class = '', '', ''

    if new_password == confirm_password and message == 'Пароль удовлетворяет всем требованиям':
        confirm_message = 'Повтор пароля записан верно'
        confirm_input_class = bootstrap_class_green['input_class']
        confirm_div_class = bootstrap_class_green['div_class']

    elif new_password != confirm_password:
        confirm_message = 'Повтор пароля записан неверно'
        confirm_input_class = bootstrap_class_red['input_class']
        confirm_div_class = bootstrap_class_red['div_class']

    return confirm_input_class, confirm_div_class, confirm_message

# Страничка с изменением парроля
@app.route('/id<int:user_id>/changepassword', methods=['GET', 'POST'])
@login_required  # для того, чтобы только авторизованный пользователь мог отправить данные по этому руту
def change_password(user_id):
    message, input_class, div_class = '', '', ''
    confirm_message, confirm_input_class, confirm_div_class = '', '', ''

    old_password = None

    if request.method == 'POST':
        new_password = str(request.form['new_password'])
        input_class, div_class, message = all_check_password(new_password)

        confirm_password = str(request.form['confirm_password'])
        confirm_input_class, confirm_div_class, confirm_message = password_comparison(
            new_password, confirm_password, message)

        old_password = str(request.form['old_password'])

        # Манипуляции с БД
        # Проверка есть ли пользователь с таким паролем, идет сравнение с  паролем из БД
        # SQL-запрос к базе данных, пароль хешируется предварительно
        query = 'SELECT password_hash FROM users WHERE users.id = %s and users.password_hash = SHA2(%s, 256);'
        cursor = db.connection().cursor(named_tuple=True)
        cursor.execute(query, (user_id, old_password))
        user = cursor.fetchone()
        cursor.close()

        if confirm_message == 'Повтор пароля записан верно':
            if user:
                # SQL-запрос на обновление пароля пользователя
                query = 'UPDATE `users` SET `password_hash`= SHA2(%s, 256) WHERE users.id = %s'
                # Для перехвата ошибок (если ввели неверный пароль) оборачиваем выполнение запроса в try
                try:
                    # C помощью with можно не закрывать cursor как делали это в load_user, это будет сделано автоматически
                    with db.connection().cursor(named_tuple=True) as cursor:
                        # Подставляем в верхний запрос при помощи метода execute(принимает аргумен-запрос, передаем кортеж(tuple) со значениями)
                        cursor.execute(query, (new_password, user_id))
                        # .commit() - для окончательного добавления записи в БД
                        db.connection().commit()
                        flash('Пароль успешно изменен.', 'success')
                except mysql.connector.errors.DatabaseError:
                    # Если случались ошибка, то идет откатить эти изменения, что были внесены до этого
                    db.connection().rollback()
                    flash('При смене пароля произошел сбой!', 'danger')
                return redirect(url_for('users'))
            else:
                flash('Текущий пароль записан неверно!', 'danger')

    return render_template('change_password.html', user_id=user_id, message=message, input_class=input_class, div_class=div_class, confirm_message=confirm_message, confirm_input_class=confirm_input_class, confirm_div_class=confirm_div_class, old_password=old_password)


        # # C помощью with можно не закрывать cursor как делали это в load_user, это будет сделано автоматически
        # with db.connection().cursor(named_tuple=True) as cursor:
        #     # Подставляем в верхний запрос (под %s) при помощи метода execute(принимает аргумен-запрос, передаем кортеж(tuple) со значениями)
        #     cursor.execute(query, (user_id.id, old_password)) # кортеж с одним элементом мохдается благодаря ЗАПЯТОЙ на конце, иначе работать не будет
        #     # print(cursor.statement) - ввыводит какой запрос был выполнен в БД
        #     print(cursor.statement)
        #     # Метод fetchone() возвращает либо None, если результат пустой, либо кортеж с найденной записью, если что-то нашлось
        #     user = cursor.fetchone()

    # # SQL-запрос на обновление пароля пользователя
    # query = 'UPDATE `users` SET `password_hash`= SHA2(%s, 256) WHERE users.id = %s'
    # # Для перехвата ошибок (если ввели неверный пароль) оборачиваем выполнение запроса в try
    # try:
    #     # C помощью with можно не закрывать cursor как делали это в load_user, это будет сделано автоматически
    #     with db.connection().cursor(named_tuple=True) as cursor:
    #         # Подставляем в верхний запрос при помощи метода execute(принимает аргумен-запрос, передаем кортеж(tuple) со значениями)
    #         cursor.execute(query, (new_password, current_user.id))
    #         # .commit() - для окончательного добавления записи в БД
    #         db.connection().commit()
    #         flash('Обработка данных прошла успешно!', 'success')
    # except mysql.connector.errors.DatabaseError:
    #     # Если случались ошибка, то идет откатить эти изменения, что были внесены до этого
    #     db.connection().rollback()
    #     flash('При смене пароля произошел сбой!', 'danger')

@app.route('/test')
def test():
    info = 'info'
    # query = ''

    return render_template('test.html', info=info)
