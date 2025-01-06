from fastapi import APIRouter, HTTPException, Request
import pymysql
import json

# Define Router
anime_router = APIRouter()

@anime_router.get("/")
async def get_anime_titles(request: Request):
    try:
        # Load the JSON file
        with open('anime.json', 'r') as f:
            anime_data = json.load(f)

        # Connect to the database
        db_config = request.app.state.db_config  # Access the database config from app state
        connection = pymysql.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            cursorclass=pymysql.cursors.DictCursor
        )

        with connection.cursor() as cursor:
            # Fetch anime_id and title from the anilist_data table
            cursor.execute("SELECT anime_id, judul FROM anilist_data")
            db_data = cursor.fetchall()

        # Create a set of anime_ids from the database for quick lookup
        db_anime_ids = {str(row['anime_id']): row['judul'] for row in db_data}

        # Prepare the result list
        result = []
        for anime_id, details in anime_data.items():
            if anime_id in db_anime_ids:
                result.append({
                    'anime_id': anime_id,
                    'title': db_anime_ids[anime_id]
                })
            else:
                result.append({
                    'anime_id': anime_id,
                    'title': None  # Title not found in database
                })

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")

    finally:
        if 'connection' in locals():
            connection.close()
