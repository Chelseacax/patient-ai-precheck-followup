"""Register all blueprints with the Flask app."""
from routes.languages import bp as languages_bp
from routes.patients import bp as patients_bp
from routes.sessions import bp as sessions_bp
from routes.agent import bp as agent_bp
from routes.voice import bp as voice_bp
from routes.config import bp as config_bp
from routes.health import bp as health_bp
from routes.frontend import bp as frontend_bp


def register_routes(app):
    app.register_blueprint(languages_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(voice_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(frontend_bp)
