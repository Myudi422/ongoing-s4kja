from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from index import index_router
from resolusi import resolusi_router
from episode import episode_router
from sokuja import anime_router
from proxy import proxy_router  # Import modul proxy

# Inisialisasi aplikasi FastAPI
app = FastAPI()

# Konfigurasi CORS
origins = ["*"]  # Ganti ini dengan domain yang diizinkan untuk keamanan
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Konfigurasi database
app.state.db_config = {
    "host": "143.198.85.46",
    "user": "ccgnimex",
    "password": "aaaaaaac",
    "database": "ccgnimex",
}

# Daftarkan router
app.include_router(index_router, prefix="/anime", tags=["Index"])
app.include_router(resolusi_router, prefix="/resolusi", tags=["Resolusi"])
app.include_router(episode_router, prefix="/episode", tags=["Episode"])
app.include_router(anime_router, prefix="/api", tags=["Anime"])
app.include_router(proxy_router, prefix="/proxy", tags=["Proxy"])

# Run server
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # Membuka akses ke semua jaringan
        port=443,        # Port HTTPS
        ssl_certfile="./ongoing.ccgnimex.my.id/fullchain.pem",  # Lokasi sertifikat
        ssl_keyfile="./ongoing.ccgnimex.my.id/privkey.pem",    # Lokasi kunci privat
        workers=4        # Jalankan beberapa worker
    )

