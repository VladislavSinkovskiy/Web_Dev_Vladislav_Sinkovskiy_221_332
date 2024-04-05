import random
from flask import Flask, render_template, request, make_response
from faker import Faker

fake = Faker()

app = Flask(__name__)
application = app


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/args')
def args():
    return render_template('args.html')

@app.route('/headers')
def headers():
    return render_template('headers.html')

@app.route('/cookies')
def cookies():
    resp = make_response(render_template('cookies.html'))
    if "name" in request.cookies:
        resp.delete_cookie("name")
    else:
        resp.set_cookie("username", "cookies")
    return resp

@app.route('/form', methods=['GET', 'POST'])
def form():
    return render_template('form.html')



@app.route('/phone', methods=['GET', 'POST'])
def phone():
    def format_validate(number):

        allowed_chars = ' ()-.+0123456789'

        # Проверяем, что введенная строка состоит только из допустимых символов
        for i in number:
            if i not in allowed_chars:
                return None, 'В введенной строке встречаются недопустимые символы!'

        # Извлекаем только цифры из введенного номера
        symb = ''.join([i for i in number if i.isdigit()])

        # Проверяем допустимое количество цифр
        if len(symb) not in (10, 11):
            return None, 'Недопустимое количество цифр!'

        # Приводим номер к стандартному формату
        if len(symb) == 11 and symb.startswith('7'):
            symb = '8' + symb[1:]
        elif len(symb) == 10:
            symb = '8' + symb

        # Форматируем номер телефона
        # Создаем переменную для хранения отформатированного номера телефона
        formatted_number = ''
        # Проверяем, начинается ли номер с "+7" или "8"
        if symb.startswith(('+7', '8')):
            # Определяем префикс для номера: "8" для случая, когда номер начинается с "+7", иначе пустая строка
            prefix = '8' if symb.startswith('+7') else ''
            # Разбиваем номер на группы по три цифры и формируем список групп
            groups = [symb[i:i+3] for i in range(len(prefix), len(symb), 3)]
            # Форматируем номер, добавляя разделители "-"
            formatted_number = '-'.join(groups[:3]) + '-' + '-'.join(groups[3:])
        else:
            # Возвращаем ошибку, если номер не начинается с "+7" или "8"
            return None, 'Недопустимый ввод!'
        # Возвращаем отформатированный номер и None, так как ошибок нет
        return formatted_number, None


    if request.method == 'POST':
        phone_number = request.form['phone']
        formatted_number, error_message = format_validate(phone_number)
        if error_message:
            return render_template('phone_num.html', error=error_message, phone=phone_number)
        else:
            return render_template('phone_num.html', number=formatted_number)
    else:
        return render_template('phone_num.html')

    
if __name__ == '__main__':
    app.run(port=8000)