# coding=utf-8
"""
User blah blah
"""

from flask import Flask, Blueprint, request, render_template, flash, url_for, redirect
from flask_login import LoginManager, login_required, login_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from itsdangerous import URLSafeTimedSerializer
from flask_wtf import CSRFProtect
from flask_bcrypt import Bcrypt

import db
from user_model import UserModel
from config import DEV_DB_NAME, EXISTING_EMAIL_CODE_ERR

# creating blueprints
users_bp = Blueprint('users_bp', __name__)
main_bp = Blueprint('main_bp', __name__)

# creating flask App
app = Flask(__name__)
app.template_folder = 'templates'  # providing path to template folder
# configuring application with CSRF protection for form security
CSRFProtect(app)

# configuring application with LoginManger for @login_required and handling login requests
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'users_bp.login'

# configuring application with Bcrypt to provide hashing utilities for application
# like generating hash for password and check hash
bcrypt = Bcrypt(app)


class RegistrationForm(FlaskForm):
    """Class represents Registration Form for user"""
    email = StringField(
        'email',
        validators=[DataRequired(), Email(message=None), Length(min=6, max=40)])
    password = PasswordField(
        'password',
        validators=[DataRequired(), Length(min=6, max=25)]
    )
    confirm = PasswordField(
        'Repeat password',
        validators=[
            DataRequired(),
            EqualTo('password', message='Passwords must match.')
        ]
    )

    def validate(self):
        """Validate that user has unique email"""
        initial_validation = super(RegistrationForm, self).validate()
        if not initial_validation:
            return False
        with db.connect(DEV_DB_NAME) as db_instance:
            result = UserModel.select_by_email(db_instance, self.email.data)
        if not result.success:
            if result.code == EXISTING_EMAIL_CODE_ERR:
                self.email.errors.append("Email already registered")
            return False
        return True


class LoginForm(FlaskForm):
    """Class represents Login Form for user"""
    email = StringField('email', validators=[DataRequired(), Email()])
    password = PasswordField('password', validators=[DataRequired()])


def generate_confirmation_token(email):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=app.config['SECURITY_PASSWORD_SALT'])


def confirm_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt=app.config['SECURITY_PASSWORD_SALT'],
            max_age=expiration
        )
    except:
        return False
    return email


@users_bp.route('/register/', methods=['GET', 'POST'])
def register():
    """Registration of a user"""
    form = RegistrationForm(request.form)
    if form.validate_on_submit():
        email = str(form.email.data)
        password = str(bcrypt.generate_password_hash(form.password.data))
        user_details = dict(
            confirmed=False
        )
        with db.connect(DEV_DB_NAME) as db_instance:
            user = UserModel(db_instance, email, password, **user_details)
            user.submit()
        # TODO: email generation
        token = generate_confirmation_token(email)

        flash('A confirmation email has been sent via email.', 'success')
        return redirect(url_for('main_bp.home'))

    print('password incorrect')
    return render_template('registration.html', form=form)


@users_bp.route('/login/', methods=['GET', 'POST'])
def login():
    """ Login for the user by email and password provided to Login Form """
    form = LoginForm(request.form)
    if form.validate_on_submit():
        with db.connect(DEV_DB_NAME) as db_instance:
            result = UserModel.select_by_email(db_instance, str(form.email.data))

        if result.count:
            user = result.documents
            # FIXME (Alena): correct hashing and verifying
            if bcrypt.check_password_hash(user.password, request.form['password']):
                login_user(user)
                flash('Welcome.', 'success')
                return redirect(url_for('main_bp.home'))
        else:
            flash('Invalid email and/or password.', 'danger')
            # TODO: create a login.html template and change index.html to login.html
            return render_template('login.html', form=form)
    return render_template('login.html', form=form)


@main_bp.route('/')
@login_required
def home():
    """Index page"""
    return render_template('index.html')


if __name__ == "__main__":
    app.secret_key = 'test_key'
    # TODO: Configuration should be provided through ENV
    app.config['WTF_CSRF_ENABLED'] = True
    # app.config['WTF_CSRF_SECRET_KEY'] = 'test'
    app.config['SECRETE_KEY'] = 'test_key'
    app.config['SECURITY_PASSWORD_SALT'] = 'test_salt'
    app.register_blueprint(users_bp)
    app.register_blueprint(main_bp)
    app.run('0.0.0.0', port=5005)
