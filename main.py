import uvicorn
from config.settings import API_HOST, API_PORT, API_WORKERS

if __name__ == '__main__':
    uvicorn.run('api.app:app', host=API_HOST, port=API_PORT, workers=API_WORKERS, reload=False, log_level='info')
