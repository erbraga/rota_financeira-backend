from app.routes import saude


def registrar_blueprints(app):
    app.register_blueprint(saude.bp)
