import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv
from telebot import TeleBot

from exception import MessageNotSend, KeyNotFound

FORMAT = ('%(asctime)s | %(levelname)s | %(funcName)s - %(message)s')

PRACTICUM_TOKEN = os.getenv('YA_TOKEN')
TELEGRAM_TOKEN = os.getenv('BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


load_dotenv()


def check_tokens() -> bool:
    """проверяет доступность переменных окружения."""
    variables = [PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN]
    return all(variables)


def send_message(bot, message) -> None:
    """отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение отправлено успешно.')
    except Exception as e:
        logging.error('Сообщение не отправлено.')
        raise MessageNotSend(e)


def get_api_answer(timestamp: int) -> None:
    """Делает запрос к единственному эндпоинту API-сервиса."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': f'{timestamp}'})
        logging.debug(
            f'Запрос к '
            f'{ENDPOINT} header {HEADERS},'
            f' параметры {timestamp}'
        )
        if response.status_code != 200:
            logging.error(
                f'Ошибка при запросе к '
                f'{ENDPOINT}, header {HEADERS},'
                f' с параметрами {timestamp}')
            raise RuntimeError()
        if not response.json():
            logging.error('Ответ не json')
    except requests.exceptions.RequestException:
        raise RuntimeError()
    return response.json()


def check_response(response: dict) -> list:
    """Проверяет ответ API на соответствие документации."""
    logging.debug('Ожидаем ответ от сервера.')
    if not isinstance(response, dict):
        logging.error('Ответ не словарь.')
        raise TypeError()
    if miss_key := {'homeworks', 'current_date'} - response.keys():
        logging.error(f'В ответе ключи не найдены: {miss_key}')
        raise KeyNotFound()
    if not isinstance(response.get('homeworks'), list):
        raise TypeError()
    return response['homeworks']


def parse_status(homework: dict) -> str:
    """Извлекает из информацию о статусе домашней работы."""
    logging.debug('Получаем статус домашней работы.')
    try:
        status = homework['status']
        verdict = HOMEWORK_VERDICTS[status]
        homework_name = homework['homework_name']
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except KeyError:
        logging.error('А такого мы не ожидали.')
        raise KeyError()


def main():
    """Основная логика работы бота."""
    logging.info('Запуск')
    logging.debug('Проверка переменных окружений.')
    if not check_tokens():
        logging.critical("Один из переменных отсутсвует...")
        sys.exit(1)
    timestamp = int(time.time())
    bot = TeleBot(TELEGRAM_TOKEN)
    status_homeworks = None
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            logging.debug('Проверка есть ли новая домашная работа.')
            if homeworks:
                logging.info('Домашняя работа найдена.')
                if homeworks[0] != status_homeworks:
                    logging.info('Обнаружили новую домашнюю работу.')
                    bot.polling()
                    send_message(bot, parse_status(homeworks[0]))
                    status_homeworks = homeworks[0]
            else:
                logging.debug('Новой домашней работы не обнаруженно.')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format=FORMAT,
                        handlers=[
                            logging.FileHandler(
                                __file__ + '.log', encoding='utf-8', mode='w'),
                            logging.StreamHandler(sys.stdout)
                        ])
    main()
