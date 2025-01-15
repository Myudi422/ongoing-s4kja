from fastapi import APIRouter, HTTPException, Query, Request, Form, Depends
from fastapi.responses import JSONResponse
import pymysql
from bs4 import BeautifulSoup
import requests



proxies = {
    'http': 'socks5h://127.0.0.1:444',
    'https': 'socks5h://127.0.0.1:444',
}


# Define Router
episode_router = APIRouter()

def get_db_connection(request: Request):
    db_config = request.app.state.db_config
    return pymysql.connect(
        host=db_config['host'],
        user=db_config['user'],
        password=db_config['password'],
        database=db_config['database'],
        cursorclass=pymysql.cursors.DictCursor,
    )
def proxy_video_url(video_url):
    if "storages.sokuja.id" in video_url:
        return f"https://ongoing.ccgnimex.my.id/proxy/proxy?url={video_url}"
    return video_url


def fetch_sokuja_data(anime_id, request: Request):
    query = "SELECT slug, base_video_url FROM sokuja WHERE anime_id = %s"
    try:
        with get_db_connection(request) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (anime_id,))
                return cursor.fetchone()
    except pymysql.MySQLError as e:
        raise RuntimeError(f"Database error: {e}")

def fetch_video_time_from_db(anime_id, telegram_id, request: Request):
    query = """
        SELECT episode_number, video_time
        FROM waktu_terakhir_tontonan
        WHERE anime_id = %s AND telegram_id = %s
    """
    try:
        with get_db_connection(request) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (anime_id, telegram_id))
                return {str(row['episode_number']): str(row['video_time']) if row['video_time'] else None for row in cursor.fetchall()}
    except pymysql.MySQLError as e:
        raise RuntimeError(f"Database error: {e}")

def fetch_anime_from_db(anime_id, telegram_id, request: Request):
    query = """
        SELECT n.anime_id, n.episode_number, n.title, n.video_url, n.subtitle_links,
               n.subtitle_url, n.resolusi, n.ditonton, t.link_gambar, w.video_time
        FROM nonton n
        LEFT JOIN thumbnail t 
            ON n.anime_id = t.anime_id 
            AND n.episode_number = t.episode_number
        LEFT JOIN waktu_terakhir_tontonan w 
            ON n.anime_id = w.anime_id 
            AND n.episode_number = w.episode_number 
            AND w.telegram_id = %s
        WHERE n.anime_id = %s
        ORDER BY n.episode_number
    """
    try:
        with get_db_connection(request) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (telegram_id, anime_id))
                return cursor.fetchall()
    except pymysql.MySQLError as e:
        raise RuntimeError(f"Database error: {e}")
    
def generate_video_url(base_video_url, ep_number, is_end):
    """Generate video URL with support for V2 versions."""
    resolutions = ['480p', '360p', '720p', '1080p']
    possible_formats = []

    if is_end:
        for res in resolutions:
            possible_formats.extend([
                f"{base_video_url}{ep_number}-{res}-END.mp4",
                f"{base_video_url}{ep_number}-END-{res}.mp4",
                f"{base_video_url}{ep_number}.{res}-END.mp4",
                f"{base_video_url}{ep_number}-{res}.mp4",
                f"{base_video_url}{ep_number}-{res}V2.mp4",  # V2 versi END
                f"{base_video_url}{ep_number}.{res}.mp4",
                f"{base_video_url}{ep_number}.{res}V2.mp4"   # V2 versi file dot
            ])
    else:
        for res in resolutions:
            possible_formats.extend([
                f"{base_video_url}{ep_number}-{res}.mp4",
                f"{base_video_url}{ep_number}-{res}V2.mp4",  # Versi V2
                f"{base_video_url}{ep_number}.{res}.mp4",
                f"{base_video_url}{ep_number}.{res}V2.mp4"   # V2 versi file dot
            ])

    # Periksa URL yang valid dari kemungkinan format
    for url in possible_formats:
        if validate_video_url(url):
            return url

    # Jika tidak ada URL yang valid, kembalikan None
    return None


def validate_video_url(video_url):
    """Check if the video URL is accessible."""
    try:
        response = requests.head(video_url, allow_redirects=True, timeout=5, proxies=proxies)
        return response.status_code == 200
    except requests.RequestException:
        return False
def prioritize_resolution(episodes):
    """Prioritize entries with 'en' resolution for each episode."""
    episode_map = {}
    for episode in episodes:
        ep_key = (episode['anime_id'], episode['episode_number'])
        if ep_key not in episode_map or episode['resolusi'] == 'en':
            episode_map[ep_key] = episode
    return list(episode_map.values())

@episode_router.get("/")
async def scrape_anime(
    anime_id: str = Query(..., description="Anime ID is required"),
    telegram_id: str = Query(..., description="Telegram ID is required"),
    request: Request = None,
):
    if not anime_id or not telegram_id:
        raise HTTPException(status_code=400, detail="Anime ID and Telegram ID are required")

    episode_list = []

    try:
        sokuja_data = fetch_sokuja_data(anime_id, request)
        if sokuja_data:
            slug = sokuja_data['slug']
            base_video_url = sokuja_data['base_video_url']
            url = f"https://x1.sokuja.uk/anime/{slug}/"

            try:
                html = requests.get(url, proxies=proxies).text
                soup = BeautifulSoup(html, 'html.parser')
                episode_elements = soup.select('div.eplister ul li')

                for episode in episode_elements:
                    ep_number = episode.select_one('div.epl-num').get_text(strip=True)
                    ep_title_full = episode.select_one('div.epl-title').get_text(strip=True)
                    is_end = '(END)' in ep_title_full
                    ep_title = f"Episode {ep_number}"
                    video_url = generate_video_url(base_video_url, ep_number, is_end)
                    if video_url:
                        episode_list.append({
                            'anime_id': str(anime_id),
                            'episode_number': str(ep_number),
                            'title': ep_title,
                            'video_url': proxy_video_url(video_url),
                            'video_time': None,
                            'link_gambar': None,
                        })
            except requests.RequestException as e:
                print(f"Scraping failed for {url}: {e}")

        if not episode_list:
            rows = fetch_anime_from_db(anime_id, telegram_id, request)
            rows = prioritize_resolution(rows)  # Pilih resolusi terbaik (prioritas 'en')
            episode_list = [
                {
                    'anime_id': str(row['anime_id']),
                    'episode_number': str(row['episode_number']),
                    'title': str(row['title']),
                    'video_url': proxy_video_url(str(row['video_url'])),  # Tambahkan proxy di sini
                    'subtitle_links': str(row['subtitle_links']) if row['subtitle_links'] else None,
                    'subtitle_url': str(row['subtitle_url']) if row['subtitle_url'] else None,
                    'resolusi': str(row['resolusi']),
                    'ditonton': str(row['ditonton']),
                    'video_time': str(row['video_time']) if row['video_time'] else None,
                    'link_gambar': str(row['link_gambar']) if row.get('link_gambar') else None,
                }
                for row in rows
            ]

        video_time_data = fetch_video_time_from_db(anime_id, telegram_id, request)
        for episode in episode_list:
            ep_number = episode['episode_number']
            episode['video_time'] = video_time_data.get(ep_number)

        return episode_list

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@episode_router.post("/")
async def send_video_time(
    anime_id: str = Form(...),
    telegram_id: str = Form(...),
    video_time: str = Form(...),
    episode_number: str = Form(...),
    last_watched: str = Form(...),
    request: Request = None,
):
    try:
        conn = get_db_connection(request)
        try:
            cursor = conn.cursor()

            # Check if data exists
            check_query = """
                SELECT * FROM waktu_terakhir_tontonan 
                WHERE anime_id = %s AND telegram_id = %s AND episode_number = %s
            """
            cursor.execute(check_query, (anime_id, telegram_id, episode_number))
            result = cursor.fetchone()

            if result:
                # Update data if it exists
                update_query = """
                    UPDATE waktu_terakhir_tontonan
                    SET video_time = %s, last_watched = %s
                    WHERE anime_id = %s AND telegram_id = %s AND episode_number = %s
                """
                cursor.execute(update_query, (video_time, last_watched, anime_id, telegram_id, episode_number))
                message = "Data successfully updated."
            else:
                # Insert new data
                insert_query = """
                    INSERT INTO waktu_terakhir_tontonan (anime_id, telegram_id, video_time, episode_number, last_watched)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(insert_query, (anime_id, telegram_id, video_time, episode_number, last_watched))
                message = "Data successfully saved."

            conn.commit()

        finally:
            cursor.close()
            conn.close()

        return JSONResponse(content={"message": message}, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")
