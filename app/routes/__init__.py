from app.routes import auth, financiamentos, indices, saude, simulacoes


def registrar_blueprints(app):
    app.register_blueprint(saude.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(simulacoes.bp)
    app.register_blueprint(financiamentos.bp)
    app.register_blueprint(indices.bp)
