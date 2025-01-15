from fastapi import APIRouter, HTTPException, Query, Request, Depends
import time
import requests
import pymysql
from bs4 import BeautifulSoup

# Create Router for resolution
resolusi_router = APIRouter()

# Cache dictionary for URL validation
url_cache = {}

proxies = {
    'http': 'socks5h://127.0.0.1:444',
    'https': 'socks5h://127.0.0.1:444',
}



# Endpoint to get resolution
@resolusi_router.get("/")
async def get_resolusi(
    anime_id: str = Query(..., description="Anime ID diperlukan"),
    episode_number: str = Query(..., description="Episode Number diperlukan"),
    request: Request = None
):
    # Validasi parameter
    if not anime_id or not episode_number:
        raise HTTPException(status_code=400, detail="Anime ID dan Episode Number dibutuhkan")

    # Coba ambil data dari database
    resolutions = get_resolusi_from_sokuja(anime_id, episode_number, request)

    # Jika data dari database kosong, ambil dari tabel `nonton` (default data)
    if not resolutions:
        resolutions = get_resolusi_from_default_database(anime_id, episode_number, request)

    return resolutions

def convert_to_proxy_url(video_url):
    """Konversi URL jika berasal dari storages.sokuja.id"""
    if "storages.sokuja.id" in video_url:
        return f"https://ongoing.ccgnimex.my.id/proxy/proxy?url={video_url}"
    return video_url


def generate_resolution_urls(base_video_url, ep_number, is_end):
    """Generate possible resolution URLs for an episode with multiple resolutions."""
    resolutions = ['360p', '480p', '720p', '1080p']  # Daftar resolusi yang didukung
    potential_urls = []

    if is_end:
        # Variasi URL untuk episode terakhir (END)
        for res in resolutions:
            potential_urls.extend([
                f"{base_video_url}{ep_number}-{res}-END.mp4",
                f"{base_video_url}{ep_number}-END-{res}.mp4",
                f"{base_video_url}{ep_number}.{res}-END.mp4",
                f"{base_video_url}{ep_number}-{res}.mp4",  # Fallback non-END
                f"{base_video_url}{ep_number}.{res}.mp4"   # Fallback titik format
            ])
    else:
        # Variasi URL untuk episode biasa
        for res in resolutions:
            potential_urls.extend([
                f"{base_video_url}{ep_number}-{res}.mp4",
                f"{base_video_url}{ep_number}.{res}.mp4"
            ])

    return potential_urls



def validate_video_url(video_url):
    """Check if the video URL is accessible with caching for optimization."""
    # Check if the URL is in cache
    if video_url in url_cache:
        cache_entry = url_cache[video_url]
        # If cache is less than 5 minutes old, return cached result
        if time.time() - cache_entry['timestamp'] < 300:  # 5 minutes
            return cache_entry['is_valid']

    # If not in cache or cache expired, validate URL
    try:
        response = requests.head(video_url, allow_redirects=True, timeout=5, proxies=proxies)
        is_valid = response.status_code == 200
    except requests.RequestException:
        is_valid = False

    # Save result to cache
    url_cache[video_url] = {
        'is_valid': is_valid,
        'timestamp': time.time()
    }

    return is_valid

def get_resolusi_from_sokuja(anime_id, episode_number, request):
    """Function to read resolutions from sokuja table in the database"""
    db_config = request.app.state.db_config  # Ambil konfigurasi dari app state

    try:
        connection = pymysql.connect(**db_config)
        cursor = connection.cursor(pymysql.cursors.DictCursor)

        # Query untuk mendapatkan data dari tabel sokuja
        query = """
        SELECT base_video_url, slug
        FROM sokuja
        WHERE anime_id = %s
        """
        cursor.execute(query, (anime_id,))
        anime_data = cursor.fetchone()

        if not anime_data:
            return []

        base_video_url = anime_data['base_video_url']
        anime_slug = anime_data['slug']
        url = f'https://x1.sokuja.uk/anime/{anime_slug}/'

        # Fetch the anime page
        html = requests.get(url, proxies=proxies).text
        soup = BeautifulSoup(html, 'html.parser')
        episodes = soup.select('div.eplister ul li')

        resolutions = []

        # Loop through episodes and find the relevant episode
        for episode in episodes:
            ep_number = episode.select_one('.epl-num').text.strip()
            ep_title_full = episode.select_one('.epl-title').text.strip()

            if ep_number == episode_number:
                is_end = '(END)' in ep_title_full

                # Generate potential URLs for all resolutions
                potential_urls = generate_resolution_urls(base_video_url, ep_number, is_end)

                for url in potential_urls:
                    if validate_video_url(url):  # Use caching in URL validation
                        # Tentukan resolusi berdasarkan URL
                        for res in ['360p', '480p', '720p', '1080p']:
                            if res in url:
                                resolusi = res.upper()
                                break

                        resolutions.append({
                            'resolusi': resolusi,
                            'video_url': convert_to_proxy_url(url)  # Konversi jika perlu
                        })

                break

        return resolutions

    except pymysql.MySQLError as e:
        print(f"Database error: {e}")
        return []

    finally:
        if connection:
            connection.close()


def get_resolusi_from_default_database(anime_id, episode_number, request):
    """Function to read resolutions from the default `nonton` table"""
    db_config = request.app.state.db_config  # Ambil konfigurasi dari app state

    try:
        connection = pymysql.connect(**db_config)
        cursor = connection.cursor(pymysql.cursors.DictCursor)

        query = """
        SELECT resolusi, video_url
        FROM nonton
        WHERE anime_id = %s AND episode_number = %s
        """
        cursor.execute(query, (anime_id, episode_number))
        rows = cursor.fetchall()

        resolutions = []
        for row in rows:
            resolusi = row['resolusi']
            if resolusi == 'en':
                resolusi = 'HD'
            elif resolusi == 'pt':
                resolusi = 'SD'

            resolutions.append({
                'resolusi': resolusi,
                'video_url': convert_to_proxy_url(row['video_url'])  # Konversi jika perlu
            })

        return resolutions

    except pymysql.MySQLError as e:
        print(f"Database error: {e}")
        return []

    finally:
        if connection:
            connection.close()
