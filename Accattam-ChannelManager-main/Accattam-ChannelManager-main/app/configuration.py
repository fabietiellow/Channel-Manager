"""Flask Configuration Class"""
import os
import secrets

class Config(object):
    """Configuration base, for all environments"""
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True

    # Secret Key per flask login
    SECRET_KEY = 'chiave-segreta-tesi'


class DevelopmentConfig(Config):
    """Development Configuration"""
    DEBUG = True

class TestingConfig(Config):
    """Testing Configuration"""
    TESTING = True
