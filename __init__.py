from flask import Flask
from app.models import db
from app.auth_udg.routes import auth_udg

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_udg.db'
    app.config['SECRET_KEY'] = 'clave-super-segura'

    db.init_app(app)
    app.register_blueprint(auth_udg)

    with app.app_context():
        db.create_all()

    return app
