from flask import Flask
from whatsapp import whatsapp_bp
import os

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")
    app.register_blueprint(whatsapp_bp, url_prefix="/whatsapp")
    @app.route("/")
    def root():
        return "OK - open /whatsapp"
    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
