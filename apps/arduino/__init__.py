# -*- encoding: utf-8 -*-

from flask import Blueprint

blueprint = Blueprint(
    'arduino_blueprint',
    __name__,
    url_prefix='/arduino'
)