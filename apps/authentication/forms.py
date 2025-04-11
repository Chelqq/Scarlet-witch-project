# -*- encoding: utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import Email, DataRequired, Length

# login and registration


class LoginForm(FlaskForm):
    username = StringField('Username',  
                         id='username_login',
                         validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField('Password',
                             id='pwd_login',
                             validators=[DataRequired(), Length(min=2, max=20)])
    remember = BooleanField('Remember me')


class CreateAccountForm(FlaskForm):
    username = StringField('Username',
                         id='username_create',
                         validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email',
                      id='email_create',
                      validators=[DataRequired(), Email()])
    password = PasswordField('Password',
                             id='pwd_create',
                             validators=[DataRequired(), Length(min=2, max=20)])
