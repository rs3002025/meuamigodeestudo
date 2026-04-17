from flask import Flask, jsonify

from routes.avaliacao_routes import avaliacao_bp
from routes.onboarding_routes import onboarding_bp
from routes.plano_routes import plano_bp
from routes.tarefa_routes import tarefa_bp


def create_app() -> Flask:
    app = Flask(__name__, static_folder="public", static_url_path="")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "amigo-de-estudo"})

    app.register_blueprint(onboarding_bp, url_prefix="/api/onboarding")
    app.register_blueprint(plano_bp, url_prefix="/api/plano")
    app.register_blueprint(tarefa_bp, url_prefix="/api/tarefas")
    app.register_blueprint(avaliacao_bp, url_prefix="/api/avaliacao")

    @app.get("/")
    def home():
        return app.send_static_file("index.html")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)
