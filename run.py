# -*- encoding: utf-8 -*-

import os
from flask_migrate import Migrate
from flask_minify import Minify
from sys import exit
from flask import Response

from apps.config import config_dict
from apps import create_app, db

# Importamos las funciones desde el archivo video_processing.py
from video_processing import gen_video_feed

# WARNING: Don't run with debug turned on in production!
DEBUG = (os.getenv('DEBUG', 'False') == 'True')

# The configuration
get_config_mode = 'Debug' if DEBUG else 'Production'

try:
    # Load the configuration using the default values
    app_config = config_dict[get_config_mode.capitalize()]
except KeyError:
    exit('Error: Invalid <config_mode>. Expected values [Debug, Production] ')

app = create_app(app_config)
Migrate(app, db)

if not DEBUG:
    Minify(app=app, html=True, js=False, cssless=False)

if DEBUG:
    app.logger.info('DEBUG       = ' + str(DEBUG))
    app.logger.info('DBMS        = ' + app_config.SQLALCHEMY_DATABASE_URI)
    app.logger.info('ASSETS_ROOT = ' + app_config.ASSETS_ROOT)

@app.route('/video_feed_0')
def video_feed_0():
    return Response(gen_video_feed(1), # si, asi aparecen en orden
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed_1')
def video_feed_1():
    return Response(gen_video_feed(0), # si, asi aparecen en orden
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    app.run()
