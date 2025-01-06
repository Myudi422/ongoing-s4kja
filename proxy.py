from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import requests

proxy_router = APIRouter()

@proxy_router.get("/proxy")
def proxy(url: str):
    """
    Proxy endpoint to fetch and forward video content using requests.
    """
    if not url:
        raise HTTPException(status_code=400, detail="Error: No URL provided")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
        "Referer": "https://storages.sokuja.id",
    }

    try:
        # Send the request to the target server
        response = requests.get(url, headers=headers, stream=True)

        # Create a streaming response to forward the content
        return StreamingResponse(
            response.iter_content(chunk_size=1024),
            media_type=response.headers.get('Content-Type', 'application/octet-stream'),
            status_code=response.status_code,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error: Unable to fetch the URL. Details: {str(e)}")
