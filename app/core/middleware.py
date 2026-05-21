import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from core.observability import observability
import logging

logger = logging.getLogger(__name__)

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            if request.url.path != "/health":
                observability.record_request(
                    endpoint=request.url.path,
                    method=request.method,
                    status_code=response.status_code,
                    response_time=process_time
                )
            
            if response.status_code == 500:
                logger.warning(f"Server error on {request.method} {request.url.path}")
            
            if process_time > 1.0:
                logger.warning(f"Slow request: {request.method} {request.url.path} - {process_time:.2f}s")
            
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(f"Error on {request.method} {request.url.path}: {str(e)}")
            raise
