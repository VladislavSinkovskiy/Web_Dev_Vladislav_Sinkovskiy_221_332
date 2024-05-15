from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user
from flask import render_template, Blueprint, request, redirect, url_for, flash, current_app
from app import db
from users_policy import UsersPolicy
from functools import wraps

# Создается объект "bp" типа Blueprint для модуля "auth" в приложении Flask с именем "name".
#  При обращении к маршрутам модуля "auth", они будут иметь префикс "/auth".
bp = Blueprint('auth', __name__, url_prefix='/auth')

# Функция "init_login_manager" создает и настраивает объект "login_manager" класса "LoginManager"
# для управления аутентификацией пользователей в приложении Flask
def init_login_manager(app):
	login_manager = LoginManager()
	# Создан экземпляр класса
	login_manager.init_app(app)
	# Даем приложению знать о существования логин менеджера
	login_manager.login_view = 'auth.login'
	login_manager.login_message = 'Для доступа к этой странице нужно авторизироваться.'
	login_manager.login_message_category = 'warning'

	# функция "load_user" будет вызвана при каждой следующей авторизации пользователя,
	#  чтобы получить информацию о пользователе из базы данных или источника данных
	login_manager.user_loader(load_user)

#  Flask-Login будет использовать атрибут "id" объекта User в качестве идентификатора
#  пользователя в сессии Flask-Login
class User(UserMixin):
    def __init__(self, user_id, user_login, role_id):
        self.id = user_id
        self.login = user_login
        self.role_id = role_id
        
	# Возвращает тру, если пользователь админ, и фолс, если нет
    def is_admin(self):
        # Сравнивается Id роли с админским
        return self.role_id == current_app.config['ADMIN_ROLE_ID']
    
	# Метод, отвечающий за проверку прав
	# Метод `can` создает экземпляр класса `UsersPolicy` с переданной записью и подгружает
	#  метод `action` этого класса, который отвечает за проверку полномочий пользователя на
	#  выполнение данного действия. Если метод найден, то он вызывается и возвращается его
	#  результат. Если метод не найден, то возвращается `False`.
    def can(self, action, record = None):
        users_policy = UsersPolicy(record)
        method = getattr(users_policy, action, None)
        if method:
            return method()
        return False

# Декоратор для проверки прав доступа к страничке, для исбежания повторения кода
def permission_check(action):
    def decor(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            user_id = kwargs.get('user_id')
            user = None
            if user_id:
                user = load_user(user_id)
            if not current_user.can(action, user):
                flash('Недостаточно прав для выполнения данного действия.', 'warning')
                return redirect(url_for('users'))
            return function(*args, **kwargs)
        return wrapper
    return decor

@bp.route('/logout', methods=['GET'])
def logout():
    logout_user()
    return redirect(url_for('index'))

# Страница c аутентификация пользователей
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']
        remember = request.form.get('remember_me') == 'on'

        # SQL-запрос к базе данных, пароль хешируется предварительно
        query = 'SELECT * FROM users WHERE login = %s and password_hash = SHA2(%s, 256);'

        # 1' or '1' = '1' LIMIT 1#
        # user'#
        # query = f"SELECT * FROM users WHERE login = '{login}' and password_hash = SHA2('{password}', 256);"

        # C помощью with можно не закрывать cursor как делали это в load_user, это будет сделано автоматически
        with db.connection().cursor(named_tuple=True) as cursor:
            # Подставляем в верхний запрос (под %s) при помощи метода execute(принимает аргумен-запрос, передаем кортеж(tuple) со значениями)
            # кортеж с одним элементом мохдается благодаря ЗАПЯТОЙ на конце, иначе работать не будет
            cursor.execute(query, (login, password))
            # print(cursor.statement) - ввыводит какой запрос был выполнен в БД
            print(cursor.statement)
            # Метод fetchone() возвращает либо None, если результат пустой, либо кортеж с найденной записью, если что-то нашлось
            user = cursor.fetchone()

        if user:
            login_user(User(user.id, user.login, user.role_id), remember=remember)
            flash('Вы успешно прошли аутентификацию!', 'success')
            param_url = request.args.get('next')
            return redirect(param_url or url_for('index'))
        flash('Введён неправильный логин или пароль.', 'danger')
    return render_template('login.html')

# Функция загрузки пользователя по идентификатору из БД
def load_user(user_id):
    # SQL-запрос к базе данных / %s работает как .format() - позволяет подставлять значение
    query = 'SELECT * FROM users WHERE users.id = %s;'
    # У объекта соединения есть метод курсор. Через метод cursor выпонлятся запрос
    # named_tuple=True - позволяет обращаться далее по названию полей таблицы БД
    cursor = db.connection().cursor(named_tuple=True)
    # Подставляем в верхний запрос (под %s) при помощи метода execute(принимает аргумен-запрос, передаем кортеж(tuple) со значениями)
    # кортеж с одним элементом создается благодаря ЗАПЯТОЙ на конце, иначе работать не будет
    cursor.execute(query, (user_id,))
    # Метод fetchone() возвращает либо None, если результат пустой, либо кортеж с найденной записью, если что-то нашлось
    user = cursor.fetchone()
    # После всех манипуляций закрываем метод cursor
    cursor.close()
    # Далее идет проверка
    # Если нашелся прользователь в БД по такому id, то возвращается объект класса user с данными этого пользователя
    # Если не нашелся, то возвращается None
    if user:
        # Возвращает id пользователя и его логин
        return User(user.id, user.login, user.role_id)
    return None
