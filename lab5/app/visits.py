# Импорт необходимых модулей и объектов
import io
from flask import render_template, Blueprint, request, send_file
from app import db, app
from math import ceil
from flask_login import current_user, login_required

# Определение количества записей на страницу
PER_PAGE = 10

# Создание объекта для маршрутизации и установки префикса для URL
bp = Blueprint('visits', __name__, url_prefix='/visits')

# Импортирует декоратор
from auth import permission_check, init_login_manager

init_login_manager(app)

@bp.route('/')
@login_required
def logging():
    # Извлекаем номер страницы из GET-параметра 'page',
    # если параметр не задан, то используем значение по умолчанию - 1
    page = request.args.get('page', 1, type=int)

    # Проверяем роль текущего пользователя.
    # Если пользователь с ролью, позволяющей просматривать статистику, то
    # отображаем все записи лога посещений;
    if current_user.can('show_statistics'):
        # Формируем запрос на получение всех записей лога посещений
        query = ('SELECT action_logs.*, users.login '
                'FROM users RIGHT JOIN action_logs ON action_logs.user_id = users.id '
                'ORDER BY created_at DESC LIMIT %s OFFSET %s')
        with db.connection().cursor(named_tuple=True) as cursor:
            cursor.execute(query, (PER_PAGE, (page-1)*PER_PAGE))
            # Получаем все записи лога посещений
            logs = cursor.fetchall()
        # Формируем запрос на получение количества всех записей лога посещений
        query = 'SELECT COUNT(*) AS count FROM action_logs'
        with db.connection().cursor(named_tuple=True) as cursor:
            cursor.execute(query)
            # Получаем количество всех записей лога посещений
            count = cursor.fetchone().count
    # Иначе, пользователь не может просматривать все записи лога посещений, а может просматривать
    # только свою историю посещений
    else:
        # Формируем запрос на получение всех записей лога посещений для конкретного пользователя
        query = ('SELECT action_logs.*, users.login '
                'FROM action_logs RIGHT JOIN users ON action_logs.user_id = users.id WHERE users.id=%s '
                'ORDER BY created_at DESC LIMIT %s OFFSET %s')
        with db.connection().cursor(named_tuple=True) as cursor:
            cursor.execute(query, (current_user.id, PER_PAGE, (page-1)*PER_PAGE))
            # Получаем только записи лога посещений, относящиеся к текущему пользователю
            logs = cursor.fetchall()
        # Формируем запрос на получение количества записей лога посещений для текущего пользователя
        query = 'SELECT COUNT(*) AS count FROM action_logs WHERE action_logs.user_id = %s'
        with db.connection().cursor(named_tuple=True) as cursor:
            cursor.execute(query, (current_user.id, ))
            # Получаем количество записей лога посещений для текущего пользователя
            count = cursor.fetchone().count

    # Вычисляем число страниц результата поиска
    last_page = ceil(count/PER_PAGE)

    # Если пользователь запрашивает загрузку CSV-файла, он может получать все записи
    if request.args.get('download_csv'):
        # Формируем запрос на получение всех записей лога посещений
        query = ('SELECT action_logs.*, users.login '
                 'FROM users RIGHT JOIN action_logs ON action_logs.user_id = users.id '
                 'ORDER BY created_at DESC')
        with db.connection().cursor(named_tuple=True) as cursor:
            cursor.execute(query)
            # Получаем все записи лога посещений
            records = cursor.fetchall()
        # Генерируем временный файл, содержащий результаты запроса
        f = download_file(records, ['path', 'login', 'created_at'])
        # Отправляем файл для скачивания пользователю
        return send_file(f, mimetype='text/csv', as_attachment=True, download_name='logs.csv')

    # Отображаем страницу с записями лога посещений
    return render_template('visits/logs.html', logs=logs, last_page=last_page, current_page=page, PER_PAGE=PER_PAGE)


# Функция download_file() предназначена для преобразования списка записей `records` в CSV-файл, содержащий данные об этих записях.
# Функция принимает два параметра:
# - `records` - список записей, которые необходимо преобразовать в CSV формат
# - `fields` - список полей, которые должны быть включены в CSV файл.
def download_file(records, fields):
    '''Сначала создаем заголовок CSV файла, который содержит перечисление всех полей, отделенных запятыми и с префиксом "№". Затем мы итерируемся по каждой записи `record` в списке `records` и добавляем соответствующие значения полей в CSV файл, разделив каждое поле запятой. Для этого мы используем функцию `getattr()`, которая позволяет получить значение поля объекта записи по его имени.'''
    # Создаем заголовок CSV файла
    csv_content = '№, ' + ', '.join(fields) + '\n'
    # Обходим список записей (records), добавляем значение полей в CSV файл
    for i, record in enumerate(records):
        values = [str(getattr(record, f, '')) for f in fields]
        csv_content += f'{i + 1}, ' + ', '.join(values) + '\n'
    '''После того как все записи добавлены в CSV файл, мы оборачиваем его в объект буфера `io.BytesIO()`, записываем в него данные и перематываем его в начало (`f.seek(0)`), чтобы иметь возможность прочитать файл позднее, если это потребуется. Наконец, мы возвращаем объект буфера с содержимым CSV файла для дальнейшего использования в коде.'''
    # Создаем объект буфера и записываем в него данные CSV файла
    f = io.BytesIO()
    f.write(csv_content.encode('utf-8'))
    f.seek(0)
    # Возвращаем объект буфера с содержимым CSV файла
    return f

@bp.route('/stat/pages')
@login_required
@permission_check('show_statistics')
def pages_stat():
    # Получение номера текущей страницы из GET-параметра запроса, либо установка значения по умолчанию
    page = request.args.get('page', 1, type=int)
    # Формирование SQL-запроса на выборку страниц и их частоты посещений, сортировка по убыванию частоты посещений
    query = 'SELECT path, COUNT(*) as count FROM action_logs GROUP BY path ORDER BY count DESC LIMIT %s OFFSET %s'
    with db.connection().cursor(named_tuple=True) as cursor:
        cursor.execute(query, (PER_PAGE, (page-1)*PER_PAGE))
        records = cursor.fetchall()

    # Формирование SQL-запроса для получения общего количества записей в таблице
    query = 'SELECT COUNT(*) AS count FROM (SELECT path FROM action_logs GROUP BY path) AS paths'
    with db.connection().cursor(named_tuple=True) as cursor:
        cursor.execute(query)
        count = cursor.fetchone().count

    # Вычисление количества страниц на основе общего количества записей и количества записей на странице
    last_page = ceil(count/PER_PAGE)

    if request.args.get('download_csv'):
        query = 'SELECT path, COUNT(*) as count FROM action_logs GROUP BY path ORDER BY count DESC'
        with db.connection().cursor(named_tuple=True) as cursor:
            cursor.execute(query)
            records = cursor.fetchall()
        f = download_file(records, ['path', 'count'])
        return send_file(f, mimetype='text/csv', as_attachment=True, download_name='pages_stat.csv')
    # Отображение шаблона pages_stat.html и передача на него объекта с данными страниц, удовлетворяющих запросу,
    # а также объектов с количеством страниц и номером текущей страницы
    return render_template('visits/pages_stat.html', records=records, last_page=last_page, current_page=page, PER_PAGE=PER_PAGE)

# -------------------------------------------------------------------------

@bp.route('/stat/users')
@login_required
@permission_check('show_statistics')
def users_stat():
    # Параметр `page` извлекается из GET-параметра, если не указано, используется значение 1
    page = request.args.get('page', 1, type=int)

    # Формируется запрос на получение статистики по посещениям пользователей
    query = ('SELECT users.first_name, users.last_name, users.middle_name, COUNT(*) AS count '
        'FROM users ' 
        'RIGHT JOIN action_logs ON users.id = action_logs.user_id '
        'GROUP BY users.first_name, users.last_name, users.middle_name '
        'ORDER BY count DESC')
    with db.connection().cursor(named_tuple=True) as cursor:
        cursor.execute(query)
        # получение всех строк, удовлетворяющих условиям запроса
        records = cursor.fetchall()

    # Формируется запрос на получение количества уникальных пользователей, совершивших хотя бы одно посещение
    query = 'SELECT COUNT(DISTINCT user_id) as count FROM action_logs;'
    with db.connection().cursor(named_tuple=True) as cursor:
        cursor.execute(query)
        # Получение единственной строки с количеством
        count = cursor.fetchone().count

    # Вычисляем число страниц результата поиска
    last_page = ceil(count/PER_PAGE)

    # Если запрос на скачивание отчета в формате CSV
    if request.args.get('download_csv'):
        # Отправляем файл для скачивания пользователю
        f = download_file(records, ['first_name', 'last_name', 'middle_name', 'count'])
        return send_file(f, mimetype='text/csv', as_attachment=True, download_name='users_stat.csv')

    # Возвращаем шаблон со статистикой посещений пользователей
    return render_template('visits/users_stat.html', records=records, last_page=last_page, current_page=page, PER_PAGE=PER_PAGE)