from fastapi import FastAPI
from app.webhook.router import router


def create_app() -> FastAPI:
    app = FastAPI(title='財猿 Chaiyuan')
    app.include_router(router)

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    return app


app = create_app()
