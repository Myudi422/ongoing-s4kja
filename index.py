from fastapi import APIRouter, HTTPException, Query, Request, Depends
from bs4 import BeautifulSoup
import requests
import pymysql
import json

index_router = APIRouter()

# URL base
BASE_URL = 'https://x1.sokuja.uk/anime/'

# Peta ID Anime manual
MANUAL_ANIME_IDS = {
    'Kami no Tou Season 2': 153406,
    'Tokidoki Bosotto Russia-go de Dereru Tonari no Alya-san': 162804,
}

# Membersihkan judul
def clean_title(title):
    title = title.strip().replace('\n', '').replace('  ', ' ')
    return title.replace('Subtitle Indonesia', '').strip()

# Mendapatkan anime_id dan gambar dari database berdasarkan judul
def get_anime_data_from_database(title, conn):
    try:
        with conn.cursor() as cursor:
            query = "SELECT anime_id, image FROM anilist_data WHERE judul = %s"
            cursor.execute(query, (title,))
            result = cursor.fetchone()
            return (result[0], result[1]) if result else (None, None)
    except Exception as e:
        print(f"Database error: {e}")
        return None, None

@index_router.get("/")
async def fetch_ongoing_anime(
    status: str = Query("ongoing", description="Status anime (default: ongoing)"),
    type_: str = Query("", description="Tipe anime"),
    order: str = Query("update", description="Urutan anime"),
    request: Request = None
):
    url = f"{BASE_URL}?status={status}&type={type_}&order={order}"

    # Proxy configuration
    proxies = {
        'http': 'socks5h://127.0.0.1:444',
        'https': 'socks5h://127.0.0.1:444',
    }

    try:
        response = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36"
        }, proxies=proxies)
        response.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch data from source: {str(e)}")

    soup = BeautifulSoup(response.text, 'html.parser')
    listupd_divs = soup.find_all('div', class_='listupd')

    # Membaca isi anime.json
    try:
        with open('anime.json', 'r') as f:
            anime_data_json = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load anime.json: {str(e)}")

    ongoing_animes = []
    null_animes = []
    visited_urls = set()

    # Koneksi ke database
    db_config = request.app.state.db_config
    conn = pymysql.connect(
        host=db_config['host'],
        user=db_config['user'],
        password=db_config['password'],
        database=db_config['database'],
        charset='utf8mb4'
    )

    try:
        for div in listupd_divs:
            articles = div.find_all('article', class_='bs')

            for article in articles:
                anime_url = article.find('a')['href']

                if anime_url in visited_urls:
                    continue
                visited_urls.add(anime_url)

                image_tag = article.find('img')
                scraped_image_url = image_tag['src'] if image_tag else ''

                title_div = article.find('div', class_='tt')
                title = title_div.find('h2').text.strip() if title_div and title_div.find('h2') else title_div.text.strip() if title_div else ''
                title = clean_title(title)

                # Mendapatkan anime_id dan gambar dari database
                anime_id, database_image_url = get_anime_data_from_database(title, conn)
                if not anime_id and title in MANUAL_ANIME_IDS:
                    anime_id = MANUAL_ANIME_IDS[title]

                anime_id_available = anime_id is not None and str(anime_id) in anime_data_json

                slug = anime_url.rstrip('/').split('/')[-1]

                anime_data = {
                    'anime_id': int(anime_id) if anime_id else None,
                    'judul': title,
                    'gambar': database_image_url if database_image_url else scraped_image_url,
                    'slug': slug,
                    'latest_episode': 'NEW',
                    'anime_id_available': anime_id_available
                }

                if not anime_id:
                    null_animes.append(anime_data)
                else:
                    ongoing_animes.append(anime_data)
    finally:
        conn.close()

    return {
        'ongoing_anime_data': ongoing_animes,
        'null_anime_data': null_animes
    }