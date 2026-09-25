from app.routes import auth, saude, simulacoes


def registrar_blueprints(app):
    app.register_blueprint(saude.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(simulacoes.bp)
