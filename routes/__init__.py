from flask import Flask

def register_blueprints(app: Flask):
    """
    Importa e registra todos os blueprints da aplicação no objeto Flask.

    Args:
        app (Flask): A instância da aplicação Flask.
    """
    # Importar os blueprints aqui, dentro da função, para evitar importações circulares
    from .auth import auth_bp
    from .subjects import subjects_bp
    from .summaries import summaries_bp
    from .reviews import reviews_bp
    from .decks import decks_bp
    from .statistics import statistics_bp
    from .sync import sync_bp  
    from .flashcards import flashcards_bp
    from .flashcard_reviews import flashcard_reviews_bp 
    from .gpt_utils import gpt_utils_bp 
    

    # Registrar os blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(subjects_bp, url_prefix='/api/subjects')
    app.register_blueprint(summaries_bp, url_prefix='/api/summaries')
    app.register_blueprint(reviews_bp, url_prefix='/api/reviews')
    app.register_blueprint(decks_bp, url_prefix='/api/decks')
    app.register_blueprint(statistics_bp, url_prefix='/api/statistics')
    app.register_blueprint(sync_bp, url_prefix='/api/sync')
    app.register_blueprint(flashcards_bp, url_prefix='/api/flashcards')
    app.register_blueprint(flashcard_reviews_bp, url_prefix='/api/flashcard-reviews') 
    app.register_blueprint(gpt_utils_bp, url_prefix='/api/gpt') # <-- ADICIONAR ESTA LINHA