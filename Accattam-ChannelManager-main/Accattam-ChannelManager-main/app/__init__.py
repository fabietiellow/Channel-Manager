import os
from flask import Flask, g
from flask_login import LoginManager, current_user
from app.views import views_bp
from app.models import db, User, Shop

basedir = os.path.abspath(os.path.dirname(__file__))


def create_app(config_class="app.configuration.DevelopmentConfig"):    
    current_app = Flask(__name__, template_folder="template")
    current_app.config.from_object(config_class)
    
    # Configurazione DB
    current_app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        "sqlite:///" + os.path.join(basedir, "database.db")
    )
    current_app.config.setdefault(
        "SQLALCHEMY_TRACK_MODIFICATIONS",
        False
    )
    
    # Inizializzazione SQLAlchemy
    db.init_app(current_app)
    
    # Configurazione Flask Login
    login_manager = LoginManager()
    login_manager.login_view = 'views.login'
    login_manager.login_message = 'Devi effettuare il login per accedere a questa pagina'
    login_manager.init_app(current_app)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Prima di ogni route si verifica se l'utente è connesso
    # se è connesso viene salvato in una variabile globale
    @current_app.before_request
    def load_current_shop():
        if current_user.is_authenticated:
            if not hasattr(g, 'current_shop'):
                g.current_shop = Shop.query.get(current_user.shop_id)
    
    # Rende current_shop disponibile nei template html
    # cioè per scrivere {current_shop.name} anziché
    # render_template(current_shop=shop)
    @current_app.context_processor
    def inject_shop():
        if current_user.is_authenticated and hasattr(g, 'current_shop'):
            return dict(current_shop=g.current_shop)
        return dict(current_shop=None)
    
    # Blueprint
    current_app.register_blueprint(views_bp)
    
    return current_app

if __name__ == "__main__":
    app = create_app()
    app.run()
