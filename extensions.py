"""
Shared Flask extension singletons.
Import db from here everywhere — never create a second SQLAlchemy() instance.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
