# RustDesk Yönetim Paneli

RustDesk açık kaynak sunucusu (rustdesk-server) için web tabanlı yönetim arayüzü.

## Özellikler

- **Dashboard** - Cihaz istatistikleri, bağlantı grafikleri, anlık durum
- **Cihaz Yönetimi** - Kayıtlı cihazları görüntüleme, etiketleme, not ekleme
- **Kullanıcı Yönetimi** - RustDesk istemci kullanıcıları oluşturma/düzenleme
- **Grup Yönetimi** - Cihaz ve kullanıcıları gruplama
- **Adres Defteri** - Paylaşımlı adres defteri yönetimi
- **Bağlantı Logları** - Kim, nereye, ne zaman bağlandı
- **Denetim Logları** - Admin işlem geçmişi
- **Sunucu Ayarları** - Yapılandırma, public key görüntüleme
- **API Anahtarları** - API anahtarı oluşturma/yönetme
- **İstemci API Uyumluluğu** - RustDesk istemcileri doğrudan bağlanabilir

## Hızlı Başlangıç

### Portainer ile Kurulum (En Kolay)

Mevcut RustDesk sunucunuza sadece yönetim panelini eklemek istiyorsanız,
Portainer'da mevcut stack'inize şu servisi ekleyin:

```yaml
  rustdesk-api:
    image: ghcr.io/radamath/rustdeskapi:latest
    container_name: rustdesk-api
    restart: unless-stopped
    ports:
      - "21114:21114"
    volumes:
      - rustdesk_data:/rustdesk-data:ro
      - api_data:/app/data
    environment:
      - SECRET_KEY=buraya-guclu-bir-anahtar-yazin
      - RUSTDESK_DB=/rustdesk-data/db_v2.sqlite3
      - ADMIN_USERNAME=admin
      - ADMIN_PASSWORD=admin123
    networks:
      - shared-net
```

> `radamath` yerine GitHub kullanıcı adınızı yazın.
> `rustdesk_data` volume adının mevcut hbbs/hbbr servislerinizle aynı olduğundan emin olun.

Alternatif olarak `docker-compose.portainer.yml` dosyasını tüm servislerle birlikte
(hbbs + hbbr + api) Portainer'a stack olarak ekleyebilirsiniz.

### Docker Compose ile Tam Kurulum

```bash
# shared-net ağını oluşturun (yoksa)
docker network create shared-net

# Tüm servisleri başlatın (hbbs + hbbr + api)
docker-compose up -d --build
```

### Sadece Yönetim Paneli (Mevcut RustDesk'e Ekleme)

Zaten çalışan hbbs/hbbr'niz varsa:

```bash
docker run -d \
  --name rustdesk-api \
  --network shared-net \
  -p 21114:21114 \
  -v rustdesk_data:/rustdesk-data:ro \
  -v api_data:/app/data \
  -e SECRET_KEY=guclu-anahtar \
  -e RUSTDESK_DB=/rustdesk-data/db_v2.sqlite3 \
  -e ADMIN_PASSWORD=sifreniz \
  ghcr.io/radamath/rustdeskapi:latest
```

---

Panel şu adreste erişilebilir olacak: **http://sunucu-ip:21114**

Varsayılan giriş bilgileri:
- Kullanıcı: `admin`
- Şifre: `admin123`

### Yerel Geliştirme

```bash
pip install -r requirements.txt
python app.py
```

## Yapılandırma

Ortam değişkenleri ile yapılandırılabilir:

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `SECRET_KEY` | `change-me-in-production` | Flask gizli anahtarı |
| `RUSTDESK_DB` | `./db_v2.sqlite3` | RustDesk veritabanı yolu |
| `ADMIN_USERNAME` | `admin` | Varsayılan admin kullanıcı adı |
| `ADMIN_PASSWORD` | `admin123` | Varsayılan admin şifresi |
| `JWT_EXPIRATION_HOURS` | `24` | İstemci token süresi (saat) |

## RustDesk İstemci Yapılandırması

RustDesk istemcisinde API sunucusu olarak şu adresi girin:

```
http://<sunucu-ip>:21114
```

## Mimari

- **Backend**: Python Flask + SQLAlchemy + Gunicorn
- **Frontend**: Vanilla JS SPA + Tailwind CSS
- **Veritabanı**: SQLite (panel verileri) + RustDesk db_v2.sqlite3 (salt okunur)
- **Docker**: Multi-arch (amd64 + arm64), GHCR üzerinden dağıtım
- **Port**: 21114 (RustDesk'in standart API portu)
- **CI/CD**: GitHub Actions ile otomatik image build & push
